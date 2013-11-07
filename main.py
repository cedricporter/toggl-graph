#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Hua Liang[Stupid ET] <et@everet.org>
#

import sys
import datetime
import pprint

from tornado.httputil import url_concat
import dateutil.parser
import pytz
import tornado.escape
import tornado.gen
import tornado.httpclient
import tornado.httputil
import tornado.ioloop
import tornado.web

# tmp, just for test
data = {}

yourdate = dateutil.parser.parse('2013-11-07T22:27:00.873224+08:00')
tz = pytz.timezone("Asia/Shanghai")


username = sys.argv[1]
password = 'api_token'
MY_APP_PATH = 'https://www.toggl.com/api/v8/workspaces'


class TOGGL_API(object):
    workspaces = ("https://www.toggl.com/api/v8/workspaces", "GET")
    projects = ("https://www.toggl.com/api/v8/workspaces/%s/projects", "GET")
    tags = ("https://www.toggl.com/api/v8/workspaces/%s/tags", "GET")
    time_entries = ("https://www.toggl.com/api/v8/time_entries", "GET")


class MainHandler(tornado.web.RequestHandler):
    @tornado.gen.coroutine
    def get(self):
        ret = ""

        # workspaces
        url, method = TOGGL_API.workspaces
        res = yield tornado.httpclient.AsyncHTTPClient().fetch(
            request=url,
            method=method,
            auth_username=username,
            auth_password=password,
        )

        json = tornado.escape.json_decode(res.body)
        workspaces = json

        workspace_id = workspaces[0]["id"]
        ret += "[workspaces]\n"
        ret += pprint.pformat(workspaces)
        ret += "\n" * 2

        # projects
        url, method = TOGGL_API.projects
        url = url % workspace_id
        res = yield tornado.httpclient.AsyncHTTPClient().fetch(
            request=url,
            method=method,
            auth_username=username,
            auth_password=password,
        )

        json = tornado.escape.json_decode(res.body)
        projects = json
        ret += "[projects]\n"
        ret += pprint.pformat(projects)
        ret += "\n" * 2

        # tags
        url, method = TOGGL_API.tags
        url = url % workspace_id
        res = yield tornado.httpclient.AsyncHTTPClient().fetch(
            request=url,
            method=method,
            auth_username=username,
            auth_password=password,
        )

        json = tornado.escape.json_decode(res.body)
        tags = json
        ret += "[tags]\n"
        ret += pprint.pformat(tags)
        ret += "\n" * 2

        # time entries
        url, method = TOGGL_API.time_entries
        start_date = tz.localize(datetime.datetime(2013, 11, 7)).isoformat()
        end_date = tz.localize(datetime.datetime(2013, 11, 8)).isoformat()

        params = {"start_date": start_date,
                  "end_date": end_date, }
        url = url_concat(url, params)

        res = yield tornado.httpclient.AsyncHTTPClient().fetch(
            request=url,
            method=method,
            auth_username=username,
            auth_password=password,
        )

        json = tornado.escape.json_decode(res.body)
        time_entries = json
        ret += "[time_entries]\n"
        ret += pprint.pformat(time_entries)
        ret += "\n" * 2

        self.set_header("Content-Type", "text/plain")
        self.write(ret)


class WorkspacesHandler(tornado.web.RequestHandler):
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
        data["workspaces"] = workspaces

        self.write(pprint.pformat(workspaces))


class ProjectsHandler(tornado.web.RequestHandler):
    @tornado.gen.coroutine
    def get(self):
        # projects
        url, method = TOGGL_API.projects
        url = url % data["workspaces"][0]["id"]
        res = yield tornado.httpclient.AsyncHTTPClient().fetch(
            request=url,
            method=method,
            auth_username=username,
            auth_password=password,
        )

        projects = tornado.escape.json_decode(res.body)
        data["projects"] = projects

        self.write(pprint.pformat(projects))


class TagsHandler(tornado.web.RequestHandler):
    @tornado.gen.coroutine
    def get(self):
        url, method = TOGGL_API.tags
        url = url % data["workspaces"][0]["id"]
        res = yield tornado.httpclient.AsyncHTTPClient().fetch(
            request=url,
            method=method,
            auth_username=username,
            auth_password=password,
        )

        tags = tornado.escape.json_decode(res.body)
        self.write(pprint.pformat(tags))


class TimeEntriesHandler(tornado.web.RequestHandler):
    @tornado.gen.coroutine
    def get(self):
        url, method = TOGGL_API.time_entries
        start_date = tz.localize(datetime.datetime(2013, 11, 7)).isoformat()
        end_date = tz.localize(datetime.datetime(2013, 11, 8)).isoformat()

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
        self.write(pprint.pformat(time_entries))


application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/toggl/workspaces", WorkspacesHandler),
    (r"/toggl/projects", ProjectsHandler),
    (r"/toggl/tags", TagsHandler),
    (r"/toggl/time_entries", TimeEntriesHandler),
],
debug=True,
)

if __name__ == "__main__":
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
