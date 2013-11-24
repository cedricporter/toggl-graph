#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Hua Liang[Stupid ET] <et@everet.org>
#

import shlex
import subprocess

import sys
import os
import datetime
import pprint
import logging
import base64
import pickle
import redis

from asana import asana
from jinja2 import Environment, FileSystemLoader
from jinja2 import TemplateNotFound
from tornado.escape import xhtml_escape
from tornado.gen import coroutine, Task, Return
from tornado.httputil import url_concat
from tornado.ioloop import IOLoop
from tornado.process import Subprocess
import dateutil.parser
import pytz
import tornado.escape
import tornado.gen
import tornado.httpclient
import tornado.httputil
import tornado.ioloop
import tornado.web


logging.basicConfig(filename='log.log', level=logging.INFO)

# tempalte engine
template_path = os.path.join(os.path.dirname(__file__), "pats")
jinja2_env = Environment(loader=FileSystemLoader([template_path]),
                         autoescape=True)


DEFAULT_ENCODING = "utf-8"
USER_AGENT = "huabz"

# tmp, just for test

yourdate = dateutil.parser.parse('2013-11-07T22:27:00.873224+08:00')
tz = pytz.timezone("Asia/Shanghai")

redis_db = redis.StrictRedis(db=5)

username = sys.argv[1]
password = 'api_token'

asana_appkey = sys.argv[2]


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
    summary_report = ("https://toggl.com/reports/api/v2/summary", "GET")
    weekly_report = ("https://toggl.com/reports/api/v2/weekly", "GET")


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


class AsanaUpdateHandler(BaseRequestHandler):

    def fill_subtasks(self, api, task_id, node, level=1):
        tasks = api.get_subtasks(task_id)

        for task in tasks:
            task_dict = {"name": task["name"], "children": []}
            node["children"].append(task_dict)
            self.fill_subtasks(api, task["id"], task_dict, level + 1)

    def get(self):
        root_task_tree = []

        asana_api = asana.AsanaAPI(asana_appkey, debug=True)
        myspaces = asana_api.list_workspaces()

        workspaces = dict((work["name"], work["id"]) for work in myspaces)
        workspace_id = workspaces["Personal"]

        users = asana_api.list_users()
        users = dict((u["name"], u["id"]) for u in users)

        user_name = "Stupid ET"
        user_id = users[user_name]

        # 列出项目
        projects = asana_api.list_projects(workspace_id)
        for proj in projects:
            proj_dict = {"name": proj["name"], "children": []}
            root_task_tree.append(proj_dict)

            # 列出项目的task
            tasks = asana_api.get_project_tasks(proj["id"], True)

            # 列出task的子task
            for task in tasks:
                task_dict = {"name": task["name"], "children": []}
                proj_dict["children"].append(task_dict)
                self.fill_subtasks(asana_api, task["id"], task_dict)

        redis_db["asana_tree"] = redis_encode({"name": "ET", "children": root_task_tree})

        self.write({"name": "ET", "children": root_task_tree})


class AsanaJsonHandler(BaseRequestHandler):
    def fill_size(self, root):
        root["size"] = 20
        for child in root["children"]:
            self.fill_size(child)

    @tornado.gen.coroutine
    def get(self):
        try:
            asana_tree = redis_decode(redis_db["asana_tree"])
            self.fill_size(asana_tree)
            self.write(asana_tree)
        except KeyError:
            r = self.request
            url = "%s://%s/%s" % (r.protocol, r.host, "asana/update")

            res = yield tornado.httpclient.AsyncHTTPClient().fetch(url)

            self.write(res)


class AsanaPageHandler(BaseRequestHandler):
    def get(self):
        self.render("asana.tmpl")


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
        tags = filter(lambda t: not t["name"].startswith("ztask-"), tags)
        time_entries = redis_decode(redis_db["time_entries"])

        projects_id_dict = dict((proj["id"], proj)
                                for proj in projects)

        summary = {}

        for entry in time_entries:
            # filter tags
            entry_tags = entry["tags"]
            for i, tag in enumerate(entry_tags):
                if tag.startswith("ztask-"):
                    entry_tags[i] = "asana"

            # time
            if "start" in entry:
                entry["start"] = dateutil.parser.parse(entry["start"])
            if "stop" in entry:
                entry["stop"] = dateutil.parser.parse(entry["stop"])
                entry["duration"] = entry["stop"] - entry["start"]
            entry["start_time"] = (entry["start"] + datetime.timedelta(hours=8)) \
                .strftime("[%m-%d] %H:%M:%S")

            if "duration" in entry:
                if "pid" in entry:
                    if (entry["pid"] in summary and
                            isinstance(summary[entry["pid"]], datetime.timedelta)):
                        summary[entry["pid"]] += entry["duration"]
                    else:
                        summary[entry["pid"]] = entry["duration"]

        print summary
        for project in projects:
            if project["id"] not in summary:
                summary[project["id"]] = 0
            else:
                summary[project["id"]] = (summary[project["id"]].total_seconds() /
                                          3600.0)

        self.render("index.tmpl",
                    workspace_name=workspace_name,
                    workspace_id=workspace_id,
                    projects=projects,
                    projects_id_dict=projects_id_dict,
                    tags=tags,
                    time_entries=time_entries,
                    summary=summary,
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
        end_date = today + datetime.timedelta(days=1)
        start_date = datetime.datetime.today() - datetime.timedelta(days=5)

        start_date = tz.localize(
            datetime.datetime(start_date.year, start_date.month, start_date.day)
        ).isoformat()
        end_date = tz.localize(
            datetime.datetime(end_date.year, end_date.month, end_date.day)
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


class SummaryReportUpdateHandler(BaseRequestHandler):
    @tornado.gen.coroutine
    def get(self):
        url, method = TOGGL_API.summary_report

        workspaces = redis_decode(redis_db["workspaces"])
        params = {"user_agent": USER_AGENT,
                  "workspace_id": workspaces[0]["id"], }
        url = url_concat(url, params)

        res = yield tornado.httpclient.AsyncHTTPClient().fetch(
            request=url,
            method=method,
            auth_username=username,
            auth_password=password,
        )

        report = tornado.escape.json_decode(res.body)
        redis_db["summary_report"] = redis_encode(report)

        self.write(report)


class SummaryReportHandler(BaseRequestHandler):
    def get(self):

        report = redis_decode(redis_db["summary_report"])

        self.write(report)


class WeeklyReportUpdateHandler(BaseRequestHandler):
    @tornado.gen.coroutine
    def get(self):
        url, method = TOGGL_API.weekly_report

        today = datetime.datetime.today()
        yesterday = today - datetime.timedelta(days=1)
        until = yesterday

        workspaces = redis_decode(redis_db["workspaces"])
        params = {"user_agent": USER_AGENT,
                  "workspace_id": workspaces[0]["id"],
                  "until": until.strftime("%Y-%m-%d"),
                  }
        url = url_concat(url, params)

        res = yield tornado.httpclient.AsyncHTTPClient().fetch(
            request=url,
            method=method,
            auth_username=username,
            auth_password=password,
        )

        report = tornado.escape.json_decode(res.body)
        redis_db["week_report"] = redis_encode(report)

        self.write(report)


class WeeklyReportJsonHandler(BaseRequestHandler):
    def get(self):
        report = redis_decode(redis_db["week_report"])

        data = report["data"]

        report = []
        for day in data:
            totals = [(total if total else 0) for total in day["totals"]]
            d = {"title": day["title"]["project"],
                 "totals": totals, }
            report.append(d)

        self.write({"data": report})


class WeeklyReportTsvHandler(BaseRequestHandler):
    @tornado.gen.coroutine
    def get(self):
        try:
            report = redis_decode(redis_db["week_report"])
        except KeyError:
            r = self.request
            url = "%s://%s/%s" % (r.protocol, r.host,
                                  "toggl/report/weekly/update")
            yield tornado.httpclient.AsyncHTTPClient().fetch(url)
            report = redis_decode(redis_db["week_report"])

        data = report["data"]

        report = []
        for day in data:
            totals = [(total / 1000.0 / 60 if total else 0)
                      for total in day["totals"][:-1]]
            d = {"title": day["title"]["project"],
                 "totals": totals, }
            report.append(d)

        tsv = "date\t"
        for proj in report:
            tsv += "%s\t" % proj["title"]
        tsv += "\n"

        day_count = len(report[0]["totals"]) - 1
        today = datetime.datetime.today()
        yesterday = today - datetime.timedelta(days=1)
        start_day = yesterday - datetime.timedelta(days=day_count)
        for i in xrange(day_count + 1):
            tsv += "%s\t" % (start_day + datetime.timedelta(i)).strftime("%Y%m%d")
            for proj in report:
                tsv += "%s\t" % proj["totals"][i]
            tsv += "\n"

        self.set_header("Content-Type", "text/plain")
        self.write(tsv)


class WeeklyReportHandler(BaseRequestHandler):
    def get(self):
        self.render("report_weekly.tmpl")


@coroutine
def call_subprocess(cmd, stdin_data=None, stdin_async=True):
    """call sub process async

        Args:
            cmd: str, commands
            stdin_data: str, data for standard in
            stdin_async: bool, whether use async for stdin
    """
    stdin = Subprocess.STREAM if stdin_async else subprocess.PIPE
    sub_process = Subprocess(shlex.split(cmd),
                             stdin=stdin,
                             stdout=Subprocess.STREAM,
                             stderr=Subprocess.STREAM, )

    if stdin_data:
        if stdin_async:
            yield Task(sub_process.stdin.write, stdin_data)
        else:
            sub_process.stdin.write(stdin_data)

    if stdin_async or stdin_data:
        sub_process.stdin.close()

    result, error = yield [Task(sub_process.stdout.read_until_close),
                           Task(sub_process.stderr.read_until_close), ]

    raise Return((result, error))


class RebuildBlogHandler(BaseRequestHandler):
    @coroutine
    def get(self):
        cmd = "sh rebuild_blog.sh"
        result, error = yield call_subprocess(cmd)
        self.write(result)


application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/asana/?", AsanaPageHandler),
    (r"/asana/update", AsanaUpdateHandler),
    (r"/asana/json", AsanaJsonHandler),

    (r"/hook/rebuild_blog", RebuildBlogHandler),

    (r"/toggl/report/summary/update", SummaryReportUpdateHandler),
    (r"/toggl/report/summary", SummaryReportHandler),

    (r"/toggl/report/weekly/update", WeeklyReportUpdateHandler),
    (r"/toggl/report/weekly/json", WeeklyReportJsonHandler),
    (r"/toggl/report/weekly/tsv", WeeklyReportTsvHandler),
    (r"/toggl/report/weekly", WeeklyReportHandler),

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
