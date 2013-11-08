#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Hua Liang[Stupid ET] <et@everet.org>
#

import sys
import os
import datetime
import pprint
import logging
import base64
import pickle
import redis

from jinja2 import TemplateNotFound
from tornado.escape import xhtml_escape
from tornado.httputil import url_concat
import dateutil.parser
import pytz
import tornado.escape
import tornado.gen
import tornado.httpclient
import tornado.httputil
import tornado.ioloop
import tornado.web
from jinja2 import Environment, FileSystemLoader


logging.basicConfig(filename='log.log', level=logging.INFO)

# tempalte engine
template_path = os.path.join(os.path.dirname(__file__), "pats")
jinja2_env = Environment(loader=FileSystemLoader([template_path]),
                         autoescape=True)


DEFAULT_ENCODING = "utf-8"

# tmp, just for test

yourdate = dateutil.parser.parse('2013-11-07T22:27:00.873224+08:00')
tz = pytz.timezone("Asia/Shanghai")

redis_db = redis.StrictRedis(db=5)

username = sys.argv[1]
password = 'api_token'


def redis_encode(session_dict):
    pickled = pickle.dumps(session_dict)
    return base64.encodestring(pickled)


def redis_decode(session_data):
    pickled = base64.decodestring(session_data)
    return pickle.loads(pickled)


def to_unicode(value, encoding=DEFAULT_ENCODING):
    """递归将对象内部的所有字符串转换为unicode"""
    if isinstance(value, unicode):
        return value
    elif isinstance(value, str):
        return unicode(value, encoding)
    elif isinstance(value, dict):
        return dict((to_unicode(k), to_unicode(v))
                    for k, v in value.iteritems())
    elif isinstance(value, (list, tuple)):
        return type(value)(to_unicode(v) for v in value)
    else:
        return value


def escape_json(value):
    """递归将对象内部的所有字符串对象escape"""
    if isinstance(value, dict):
        return dict((escape_json(k), escape_json(v))
                    for k, v in value.iteritems())
    elif isinstance(value, (list, tuple)):
        return type(value)(escape_json(v) for v in value)
    elif isinstance(value, (unicode, str)):
        return xhtml_escape(value)
    else:
        return value


class TOGGL_API(object):
    workspaces = ("https://www.toggl.com/api/v8/workspaces", "GET")
    projects = ("https://www.toggl.com/api/v8/workspaces/%s/projects", "GET")
    tags = ("https://www.toggl.com/api/v8/workspaces/%s/tags", "GET")
    time_entries = ("https://www.toggl.com/api/v8/time_entries", "GET")
    time_entry_detail = ("https://www.toggl.com/api/v8/time_entries/%s", "GET")


class TemplateRendering(object):
    """
    A simple class to hold methods for rendering templates.
    """
    def render_template(self, template_name, **kwargs):
        try:
            env = self.settings["jinja2_env"]
            template = env.get_template(template_name)
        except TemplateNotFound:
            raise TemplateNotFound(template_name)
        content = template.render(kwargs)
        return content


class BaseRequestHandler(tornado.web.RequestHandler, TemplateRendering):
    def render_as_string(self, template_name, **kwargs):
        """
        This is for making some extra context variables available to
        the template
        """
        kwargs.update({
            'settings': self.settings,
            'STATIC_URL': self.settings.get('static_url_prefix', '/'),
            'STATIC_LIB_URL': self.settings.get('static_lib_url_prefix', '/'),
            'request': self.request,
            'get_xsrf_token': self.get_xsrf_token,
            'xsrf_form_html': self.xsrf_form_html,
        })
        kwargs = to_unicode(kwargs)
        content = self.render_template(template_name, **kwargs)
        return content

    def render(self, template_name, **kwargs):
        content = self.render_as_string(template_name, **kwargs)
        self.write(content)
        self.finish()

    def initialize(self):
        pass
        # self.db = self.settings["db"]

    def get_xsrf_token(self):
        """self.xsrf_token是延迟创建的，如果页面不需要就不要去执行"""
        return self.xsrf_token

    def ret_json(self, status, msg, result="", auto_escape=True, why=""):
        if auto_escape:
            result = escape_json(result)
        self.write({"status": status, "msg": msg,
                    "result": result, "why": why})
        self.finish()


class MainHandler(BaseRequestHandler):
    @tornado.gen.coroutine
    def get(self):
        try:
            workspaces = redis_decode(redis_db["workspaces"])
            workspace_name = workspaces[0]["name"]
            workspace_id = workspaces[0]["id"]
        except KeyError:
            self.redirect("/toggl/update")

        projects = redis_decode(redis_db["projects"])
        tags = redis_decode(redis_db["tags"])
        time_entries = redis_decode(redis_db["time_entries"])

        projects_id_dict = dict((proj["id"], proj)
                                for proj in projects)

        for entry in time_entries:
            if "start" in entry:
                entry["start"] = dateutil.parser.parse(entry["start"])
            if "stop" in entry:
                entry["stop"] = dateutil.parser.parse(entry["stop"])
                entry["duration"] = entry["stop"] - entry["start"]
            entry["start_time"] = entry["start"].strftime("%m-%d %H:%M:%S")

        self.render("index.tmpl",
                    workspace_name=workspace_name,
                    workspace_id=workspace_id,
                    projects=projects,
                    projects_id_dict=projects_id_dict,
                    tags=tags,
                    time_entries=time_entries,
                    )


class WorkspacesHandler(BaseRequestHandler):
    @tornado.gen.coroutine
    def get(self):
        url, method = TOGGL_API.workspaces
        res = yield tornado.httpclient.AsyncHTTPClient().fetch(
            request=url,
            method=method,
            auth_username=username,
            auth_password=password,
        )

        workspaces = tornado.escape.json_decode(res.body)
        redis_db["workspaces"] = redis_encode(workspaces)

        self.redirect("/toggl/projects")


class ProjectsHandler(BaseRequestHandler):
    @tornado.gen.coroutine
    def get(self):
        # projects
        url, method = TOGGL_API.projects
        workspaces = redis_decode(redis_db["workspaces"])
        url = url % workspaces[0]["id"]
        res = yield tornado.httpclient.AsyncHTTPClient().fetch(
            request=url,
            method=method,
            auth_username=username,
            auth_password=password,
        )

        projects = tornado.escape.json_decode(res.body)
        redis_db["projects"] = redis_encode(projects)

        logging.info(projects)

        self.redirect("/toggl/tags")


class TagsHandler(BaseRequestHandler):
    @tornado.gen.coroutine
    def get(self):
        url, method = TOGGL_API.tags
        workspaces = redis_decode(redis_db["workspaces"])
        url = url % workspaces[0]["id"]
        res = yield tornado.httpclient.AsyncHTTPClient().fetch(
            request=url,
            method=method,
            auth_username=username,
            auth_password=password,
        )

        tags = tornado.escape.json_decode(res.body)
        redis_db["tags"] = redis_encode(tags)
        self.redirect("/toggl/time_entries")

        logging.info(tags)


class TimeEntriesHandler(BaseRequestHandler):
    @tornado.gen.coroutine
    def get(self):
        url, method = TOGGL_API.time_entries

        today = datetime.datetime.today()
        tomorrow = today + datetime.timedelta(days=1)
        today = datetime.datetime.today() - datetime.timedelta(days=1)

        start_date = tz.localize(
            datetime.datetime(today.year, today.month, today.day)
        ).isoformat()
        end_date = tz.localize(
            datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day)
        ).isoformat()

        params = {"start_date": start_date,
                  "end_date": end_date, }
        url = url_concat(url, params)

        res = yield tornado.httpclient.AsyncHTTPClient().fetch(
            request=url,
            method=method,
            auth_username=username,
            auth_password=password,
        )

        time_entries = tornado.escape.json_decode(res.body)
        time_entries.reverse()
        redis_db["time_entries"] = redis_encode(time_entries)
        self.redirect("/")

        logging.info("entries params = %s\nlen = %s" % (
            params, len(time_entries)))


class TimeEntriesDetailHandler(BaseRequestHandler):
    @tornado.gen.coroutine
    def get(self):
        self.set_header("Content-Type", "text/plain")

        url, method = TOGGL_API.time_entry_detail
        time_entries = redis_decode(redis_db["time_entries"])

        for entry in time_entries:
            key = "time_entry:%s" % entry["id"]
            if redis_db.get(key):
                continue

            req_url = url % entry["id"]
            res = yield tornado.httpclient.AsyncHTTPClient().fetch(
                request=req_url,
                method=method,
                auth_username=username,
                auth_password=password,
            )

            detail = tornado.escape.json_decode(res.body)
            redis_db[key] = redis_encode(detail)
            self.write(pprint.pformat(detail))


class UpdateHandler(BaseRequestHandler):
    def get(self):
        logging.info("starting update")

        self.redirect("/toggl/workspaces")


application = tornado.web.Application([
    (r"/", MainHandler),

    (r"/toggl/update", UpdateHandler),
    (r"/toggl/workspaces", WorkspacesHandler),
    (r"/toggl/projects", ProjectsHandler),
    (r"/toggl/tags", TagsHandler),
    (r"/toggl/time_entries", TimeEntriesHandler),
    (r"/toggl/time_entries_detail", TimeEntriesDetailHandler),

    (r"/js/(.*)", tornado.web.StaticFileHandler, {"path": "htdocs/js"}),
    (r"/css/(.*)", tornado.web.StaticFileHandler, {"path": "htdocs/css"}),
    (r"/fonts/(.*)", tornado.web.StaticFileHandler, {"path": "htdocs/fonts"}),
],
debug=True,
template_path=template_path,
jinja2_env=jinja2_env,
static_lib_url_prefix="/",
static_url_prefix="/",
)

if __name__ == "__main__":
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
