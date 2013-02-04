"""
LICENSE

    pysrd - Python scripts for working with the DND35 OGL SRD.
    Copyright (C) 2012, 2013 Richard Tew

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

OVERVIEW

    Starts up on port 9000, and allows dynamic introspection of the DND35 SQLite database contents.

    Hard coded variables:

        DATABASE_FILENAME:          file name of the DND35 SQLite database.
        table_display_columns:      columns are explicitly excluded by table name.
        table_sort_column:          default sorting column for specific tables.
"""

import cgi
import sqlite3
import urlparse
import types

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from SocketServer import ThreadingMixIn


DATABASE_FILENAME = "dnd35.sqlite"

table_display_columns = {
    "abilities":            [ "id", "name", "shortname" ],
    "class":                [ "id", "name", "type" ],
    "class_table":          [ "id", "name", "level" ],
    "conditions":           [ "id", "name" ],
    "domain":               [ "id", "name" ],
    "equipment":            [ "id", "name", "family", "category", "subcategory" ],
    "feat":                 [ "id", "name", "type" ],
    "item":                 [ "id", "name", "category", "subcategory" ],
    "monster":              [ "id", "family", "name", "altname", "size", "type", "descriptor", "environment" ],
    "power":                [ "id", "name", "discipline", "subdiscipline", "descriptor" ],
    "skill":                [ "id", "name", "subtype" ],
    "special_abilities":    [ "id", "name" ],
    "spell":                [ "id", "name", "school", "subschool", "descriptor" ],
}

table_sort_column = {
    "class": "name",
}


class RequestHandler(BaseHTTPRequestHandler):
    # Respect keep alive requests.
    protocol_version = "HTTP/1.1"
    useChunked = False

    page_handlers = {}
    pages = {}

    def __init__(self, *args, **kwargs):
        BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def do_GET(self):
        scheme, netloc, path, parameters, query, fragment = urlparse.urlparse(self.path, "http")
        self.handle_command(path, query, "")

    def do_POST(self):
        scheme, netloc, path, parameters, query, fragment = urlparse.urlparse(self.path, "http")
        contentType, contentTypeParameters = cgi.parse_header(self.headers.getheader('content-type'))
        contentLength = int(self.headers.get("content-length", -1))

        content = ""
        kwargs = None
        if contentType == "multipart/form-data":
            content, multiparts = self.ExtractMultiparts(contentTypeParameters, contentLength)
        elif contentType == "application/x-www-form-urlencoded":
            query = self.rfile.read(contentLength)

        self.handle_command(path, query, content)

    def handle_command(self, path, query, content):
        kwargs = cgi.parse_qs(query, keep_blank_values=1)
        transferEncoding = self.headers.get("transfer-encoding")
        
        if transferEncoding == "chunked":
            # As I understand it the additional headers should be incorporated into
            # self.headers and "chunked" cleared from the transfer-encoding header.
            additionalHeaders, content = self.ReadChunks()

        # path == "/mud-push"
        body = None
        print "\"%s\"" % path
        if path in self.page_handlers:
            body = self.page_handlers[path](self, path, kwargs)
        elif path in self.pages:
            body = open(pages[path], "r").read()

        if body is not None:
            insert = ""
            for k, v in self.headers.items():
                insert += "%s: %s<br>" % (k, v)
            # insert += str((scheme, netloc, path, parameters, query, fragment)) +"<br>"

            body = body.replace("--BODY--", insert)

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            if self.useChunked:
                self.send_header("Transfer-Encoding", "chunked")
            else:
                self.send_header("Content-Length", len(body))
            self.end_headers()

            if self.useChunked:
                halfLen = int(len(body) / 2)
                chunk1 = body[:halfLen]
                chunk2 = body[halfLen:]

                self.WriteChunk(chunk1)
                self.WriteChunk(chunk2)
                self.WriteChunk()
            elif path.endswith(".ico") != ".":     # EXPLICIT BINARY FILES
                self.wfile.write(body)
            else:                                   # TEXT
                self.wfile.write(body.encode('ascii','xmlcharrefreplace'))
        else:
            # Page not found.
            self.send_response(404,"Page not found")
            body = "404 - Page '%s' not found." % path
            self.send_header("Content-type", "text/plain")
            self.send_header("Content-Length", len(body))
            self.end_headers()

            self.wfile.write(body)

    def ExtractMultiparts(self, contentTypeParameters, contentLength):
        initialPartBoundary = "--"+ contentTypeParameters["boundary"] +"\r\n"
        interimPartBoundary = "\r\n"+ initialPartBoundary
        finalPartBoundary = "\r\n--"+ contentTypeParameters["boundary"] +"--\r\n"
        partBoundary = initialPartBoundary

        content = ""
        contentRead = 0
        multiparts = []

        rawData = ""
        rawDataOffset = 0

        # We assume that there may be leading data before the first boundary.
        lastDataStart = 0
        while contentRead < contentLength:
            readSize = min(contentLength - contentRead, 98304)
            rawData += self.rfile.read(readSize)
            contentRead += readSize

            while 1:
                # Do we have another part header in the read data?
                headerOffset = rawData.find(partBoundary, rawDataOffset)
                if headerOffset == -1:
                    break # Read more data.

                if headerOffset > lastDataStart:
                    if lastDataStart == 0:
                        content = rawData[lastDataStart:headerOffset]
                    else:
                        multiparts[-1][1] = rawData[lastDataStart:headerOffset]

                headerOffset += len(partBoundary)
                partBoundary = interimPartBoundary

                # Do we have the end of the part header in the read data?
                dataOffset = rawData.find("\r\n\r\n", headerOffset)
                if dataOffset == -1:
                    break # Read more data.

                # Skip past the header end to the start of the data.
                dataOffset += 4
                lastDataStart = dataOffset

                # Extract the headers into a file-like object.
                sio = cStringIO.StringIO()
                sio.write(rawData[headerOffset:dataOffset])
                sio.seek(0)

                multiparts.append([ self.MessageClass(sio), None ])

                rawDataOffset = headerOffset

        # Extract the last bit of data.
        headerOffset = rawData.find(finalPartBoundary, lastDataStart)
        if headerOffset != -1:
            multiparts[-1][1] = rawData[lastDataStart:headerOffset]

        return content, multiparts

    def ReadChunks(self):
        # Possible improvement: Work out what to do with these extensions.

        def ReadChunkHeader():
            # HEX-LENGTH[;x=y]\r\n
            line = self.rfile.readline()
            bits = [ bit.strip() for bit in line.split(";") ]
            extension = None
            if len(bits) == 2:
                extension = bits[1].split("=")
            return int(bits[1], 16), extension

        data = cStringIO.StringIO()
        chunkSize, extension = ReadChunkHeader()
        while chunkSize > 0:
            data.write(self.rfile.read(chunkSize))
            self.rfile.read(2)
            chunkSize, extension = ReadChunkHeader()
        # Optional chunk trailer after the last one.
        headers = self.MessageClass(self.rfile, 0)
        return headers, data.getvalue()

    def WriteChunk(self, data=None, **kwargs):
        """
            Write a chunk of data.
            Requires that a chunked Transfer-Encoding header was set.
            If used, chunks should be finalised with a final one with no data.
        """
        data = data.encode('ascii','xmlcharrefreplace')

        xtra = ""
        for k, v in kwargs.iteritems():
            xtra += ";%s=%s"
        chunkSize = data and len(data) or 0
        self.wfile.write("%X%s\r\n" % (chunkSize, xtra))
        if data:
            self.wfile.write(data)
        self.wfile.write("\r\n")

def run():
    address = ('127.0.0.1', 9000)
    print "Starting web server on %s port %d" % address
    server = StacklessHTTPServer(address, RequestHandler)
    server.serve_forever()


#class HTTPServer(ThreadingMixIn, HTTPServer):
#    pass


def table_link(table_name, sort_column_name=None, link_text=None):
    link = "/table?name=%s" % table_name
    if sort_column_name is not None:
        link += "&sort_column="+ sort_column_name
    if link_text is None:
        link_text = table_name
    return "<a href='%s'>%s</a>" % (link, link_text)

def table_row_link(table_name, row_id):
    return "<a href='/row?table=%s&row_id=%s'>%s</a>" % (table_name, row_id, row_id)


def icon_fetcher(handler, path, kwargs):
    return open("favicon.ico", "rb").read()

RequestHandler.page_handlers["/favicon.ico"] = icon_fetcher

def page_view_row(handler, path, kwargs):
    # /row?table=<table_name>&row_id=<row_id>
    table_name = kwargs["table"][0]

    # Validate query string parameters.
    try:
        row_id = int(kwargs["row_id"][0])
    except ValueError:
        return "invalid row id parameter in query string"

    conn = sqlite3.connect(DATABASE_FILENAME)
    c = conn.cursor()
    c.execute("SELECT * FROM sqlite_master WHERE type='table'")

    column_names = [ column_info[0] for column_info in c.description ]
    idx = column_names.index("tbl_name")
    table_names = [ row[idx] for row in c ]
    table_names.sort()

    if table_name not in table_names:
        return "invalid table name parameter in query string"

    # Build response.
    c = conn.cursor()
    c.execute("SELECT * FROM %s WHERE id=%d" % (table_name, row_id))
    column_names = [ column_info[0] for column_info in c.description ]

    s = ""
    s += "<html><body>"
    s += "Back to table: "+ table_link(table_name) +"<br/><br/>"
    s += "<table border='2'>"
    for row in c:
        for idx, value in enumerate(row):
            column_name = column_names[idx]
            s += "<tr>"
            s += "<td cellpadding=5 valign=top>%s</td>" % column_name
            s += "<td cellpadding=5 valign=top>%s</td>" % value
            s += "</tr>"
    s += "</table>"
    s += "</body></html>"
    return s

RequestHandler.page_handlers["/row"] = page_view_row

def page_view_table(handler, path, kwargs):
    # /table?name=<table_name>
    table_name = kwargs["name"][0]

    sort_column_name = None
    if "sort_column" in kwargs:
        sort_column_name = kwargs["sort_column"][0]

    # Build response.
    conn = sqlite3.connect(DATABASE_FILENAME)
    s = ""
    s += "<html><body>"
    s += "Back to <a href='/'>table list</a>.<br/><br/>"

    c = conn.cursor()
    show_columns = table_display_columns.get(table_name, None)
    if show_columns is None:
        column_part = "*"
    else:
        column_part = ",".join(show_columns)
    c.execute("SELECT %s FROM %s" % (column_part, table_name))
    column_names = [ column_info[0] for column_info in c.description ]

    for idx, column_name in enumerate(column_names):
        if idx > 0:
            s += ", "
        if show_columns is None or column_name not in show_columns:
            s += column_name
        else:
            s += "["+ column_name +"]"

    s += "<table border='1'>"
    s += "<tr>"
    for column_name in column_names:
        if show_columns is None or column_name in show_columns:
            s += "<td>%s</td>" % table_link(table_name, column_name, column_name)
    s += "</tr><br/><br/>"

    lines = []
    for row in c:
        line = []
        for idx, value in enumerate(row):
            column_name = column_names[idx]
            if show_columns is None or column_name in show_columns:
                if type(value) in types.StringTypes:
                    line.append(value.encode('ascii','xmlcharrefreplace'))
                else:
                    line.append(value)
        lines.append(line)

    if sort_column_name is None or sort_column_name not in column_names:
        sort_column_name = table_sort_column.get(table_name, None)
    if sort_column_name is None and "name" in column_names:
        sort_column_name = "name"
    if sort_column_name is not None:
        idx = column_names.index(sort_column_name)
        lines.sort(lambda a, b: cmp(a[idx], b[idx]))

    for line in lines:
        s += "<tr>"
        for idx, value in enumerate(line):
            column_name = column_names[idx]
            if column_name == "id":
                value = table_row_link(table_name, value)
            s += "<td valign=top>%s</td>" % value
        s += "</tr>"

    s += "</table>"
    s += "</body></html>"
    return s

RequestHandler.page_handlers["/table"] = page_view_table

def page_list_tables(hander, path, kwargs):
    conn = sqlite3.connect(DATABASE_FILENAME)
    s = ""
    s += "<html><body>"
    c = conn.cursor()
    c.execute("SELECT * FROM sqlite_master WHERE type='table'")

    column_names = [ column_info[0] for column_info in c.description ]
    idx = column_names.index("tbl_name")
    table_names = [ row[idx] for row in c ]
    table_names.sort()

    s += "dnd35.sqlite tables:<br/><br/>"
    s += "<table border='1'>"
    for table_name in table_names:
        s += "<tr>"
        s += "<td>%s</td>" % table_link(table_name)
        s += "</tr>"
    s += "</table>"
    s += "</body></html>"
    return s

RequestHandler.page_handlers["/"] = page_list_tables
RequestHandler.page_handlers["/home"] = page_list_tables

def run():
    address = ('127.0.0.1', 9000)
    print "Starting web server on %s port %d" % address
    server = HTTPServer(address, RequestHandler)
    server.serve_forever()


if __name__ == "__main__":
    run()
    print "Main thread exited"


# c.execute("SELECT * FROM monster WHERE type='Humanoid'")
# c.execute("SELECT DISTINCT family FROM monster WHERE type='Humanoid'")
