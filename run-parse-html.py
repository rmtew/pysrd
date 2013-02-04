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

    The SQLite database provided by highmage, and available here
    (http://www.andargor.com/) lacks some data from the SRD.  This script
    parses additional SRD information from Josh Ritter's OpenSRD
    (http://sourceforge.net/projects/opensrd) HTML files.

    You will need to ensure the following variables have the correct values:
        DATABASE_FILENAME:  Name of a local file containing the SQLite database
                            created by highmage.
        HTML_DIR_NAME:      Name of local directory immediately containing the
                            OpenSRD html files.

    Additionally, generally unparseable data is hard-coded into a secondary
    script and will be injected directly into custom tables.
"""

import bs4 # c:\python27\Scripts\pip.exe install beautifulsoup4
import os
import re
import sys
import StringIO
import sqlite3


DATABASE_FILENAME = "dnd35.sqlite"
HTML_DIR_NAME = "SRD-html"


# Taken from the Python wiki.
html_escape_table = {
    # "&": "&amp;",
    '"': "&quot;",
    "'": "&apos;",
    ">": "&gt;",
    "<": "&lt;",
}
def html_escape(text):
    """Produce entities within text."""
    return "".join(html_escape_table.get(c,c) for c in text) 


def escape_children(v):
    for child in v.contents:
        if isinstance(child, bs4.Tag):
            if child.name == "a":
                if child.string is None:
                    child.replace_with("")
                    continue
                child.string = html_escape(child.string)
            escape_children(child)
        else:
            child.replace_with(html_escape(child))


#####

def parse_special_abilities(cb):
    file_path = os.path.join(html_path, "abilitiesAndConditions.html")
    with open(file_path, "r") as f:
        soup = bs4.BeautifulSoup(f)
        v = first_h5 = soup.body.h5

        name = ""
        fulltext = ""
        while v:
            if isinstance(v, bs4.Tag):
                if v.name == "h5":
                    # Commit any current entry.
                    if name:
                        for name in name.split("and"):
                            cb(name=name.strip().capitalize(), fulltext=fulltext)
                    # Start the next entry.
                    name = v.get_text().lower()
                    fulltext = ""
                elif v.name == "h3":
                    break
                else:
                    if "class" in v.attrs:
                        del v.attrs["class"]
                    fulltext += v.prettify()
            else:
                pass # print v.string
            v = v.next_sibling
        # Commit any current entry.
        if name:
            for name in name.split("and"):
                cb(name=name.strip().capitalize(), fulltext=fulltext)


def parse_conditions(cb):
    file_path = os.path.join(html_path, "abilitiesAndConditions.html")
    with open(file_path, "r") as f:
        soup = bs4.BeautifulSoup(f)
        v  = soup.body.h3.find_next("h3")
        if v.get_text() != "CONDITIONS":
            raise Exception, "unable to find CONDITIONS H3 tag"
        v = v.find_next("p")

        name = ""
        fulltext = ""
        while v:
            if "class" not in v.attrs:
                b = v.find("b")
                if b is None:
                    fulltext += v.prettify()
                else:
                    # Commit any current entry.
                    if name:
                        cb(name=name, fulltext=fulltext)
                    # Start the next entry.
                    name = b.get_text().lower().capitalize()
                    escape_children(v)
                    fulltext = v.prettify()
            v = v.find_next("p")
        # Commit any current entry.
        if name:
            cb(name=name, fulltext=fulltext)

def parse_abilities(cb):
    title_re = re.compile("([a-zA-Z]+)[ ]+\(([a-zA-Z]+)\)")

    file_path = os.path.join(html_path, "basics.html")
    with open(file_path, "r") as f:
        soup = bs4.BeautifulSoup(f)
        v  = soup.body.h3.find_next("h3")
        while v.get_text() != "THE ABILITIES":
            v  = v.find_next("h3")

        v  = v.find_next("h5")
        name = ""
        shortname = ""
        fulltext = ""
        while v:
            if isinstance(v, bs4.Tag):
                if v.name == "h5":
                    # Commit any current entry.
                    if name:
                        cb(name=name, shortname=shortname, fulltext=fulltext)
                    # Start the next entry.
                    m = title_re.match(v.get_text().lower())
                    name = m.group(1).capitalize()
                    shortname = m.group(2)
                    fulltext = ""
                elif v.name == "h3":
                    break
                else:
                    if "class" in v.attrs:
                        del v.attrs["class"]
                    fulltext += v.prettify()
            else:
                pass # print v.string
            v = v.next_sibling
        # Commit any current entry.
        if name:
            cb(name=name, shortname=shortname, fulltext=fulltext)

def parse_abilities_table(cb):
    file_path = os.path.join(html_path, "basics.html")
    with open(file_path, "r") as f:
        soup = bs4.BeautifulSoup(f)

        v  = soup.body.h5
        while v.get_text() != "ABILITY MODIFIERS":
            v = v.find_next("h5")

        e = v.find_next("tr")
        tr_column_names = []
        tr_lines = []
        while e:
            if isinstance(e, bs4.Tag):
                if e.name == "tr":
                    if e.th is not None:
                        # The last row with header cells is considered the right one.
                        tr_column_names[:] = []
                        th = e.th
                        while th:
                            if isinstance(th, bs4.Tag):
                                if "colspan" in th.attrs:
                                    colspan = int(th.attrs["colspan"])
                                    tr_column_names.extend(( "?" for i in range(colspan) ))
                                else:
                                    v = th.get_text().lower()
                                    tr_column_names.append(th.get_text().lower())
                            th = th.next_sibling
                    elif e.td is not None:
                        td = e.td
                        line = []
                        while td:
                            if isinstance(td, bs4.Tag):
                                if "colspan" in td.attrs:
                                    colspan = int(td.attrs["colspan"])
                                    if colspan != len(tr_column_names):
                                        line.extend(( "NULL" for i in range(colspan) ))
                                else:
                                    value = td.get_text()
                                    if value == u'\u2014': # unicode for '-'
                                        value = 0
                                    else:
                                        try:
                                            value = int(value)
                                        except ValueError:
                                            pass
                                    line.append(value)
                            td = td.next_sibling
                        if len(line) == len(tr_column_names):
                            tr_lines.append(line)
            elif len(e.string) > 1:
                pass # print "'"+ e +"'"
            e = e.next_sibling

        # Translate the table column names to database column names.
        db_column_names = []
        column_types_list = []
        for i, column_name in enumerate(tr_column_names):
            if i == 0:
                db_column_names.append(column_name +"_min")
                column_types_list.append((db_column_names[-1], "INTEGER"))
                db_column_names.append(column_name +"_max")
                column_types_list.append((db_column_names[-1], "INTEGER"))
            else:
                c = column_name[0]
                try:
                    int(column_name[0])
                    value = "level_"+ column_name[0]
                except ValueError:
                    value = column_name
                db_column_names.append(value)
                column_types_list.append((db_column_names[-1], "INTEGER"))

        # Fix the first column.
        db_lines = []
        for tr_line in tr_lines:
            db_line = []
            score_range = tr_line[0]
            if type(score_range) is int:
                score_min = score_max = score_range
            else:
                score_min, score_max = [ int(v) for v in score_range.split("-") ]
            db_line.append(score_min)
            db_line.append(score_max)
            db_line.extend(tr_line[1:])
            db_lines.append(db_line)

        for db_line in db_lines:
            kwargs = dict(zip(db_column_names, db_line))
            kwargs["column_types_list"] = column_types_list
            cb(**kwargs)


# This list is used to preserve column ordering.
column_types_list = [
    ("name",         "TEXT NOT NULL UNIQUE"),
    ("shortname",    "TEXT NOT NULL UNIQUE"),
    ("fulltext",     "TEXT NOT NULL"),
]


def create_callback(table_name, statements):
    def cb(**kwargs):
        # Build the complete list of known column types for this table.
        local_column_types_list = column_types_list[:]
        if "column_types_list" in kwargs:
            local_column_types_list.extend(kwargs["column_types_list"])
            del kwargs["column_types_list"]
        local_column_types = dict(local_column_types_list)
        input_column_names = kwargs.keys()

        # Validate text has sane values.
        for column_name in input_column_names:
            column_type = local_column_types[column_name]
            if "TEXT" in column_type and "'" in kwargs[column_name]:
                raise RuntimeError("text contains SQL quoting character")

        # Build the table definition on receiving the first row to insert.
        if not len(statements):
            s = StringIO.StringIO()
            # Drop the table if it already exists, to start fresh.
            s.write("DROP TABLE IF EXISTS %s;" % table_name)
            statements.append(s.getvalue())
            s.close()

            # Recreate the table, preserving ideal column ordering.
            s = StringIO.StringIO()
            s.write("CREATE TABLE %s (" % table_name)
            s.write("id INTEGER PRIMARY KEY, ")
            cnt = 0
            for entry in local_column_types_list:
                if entry[0] in input_column_names:
                    if cnt > 0:
                        s.write(", ")
                    s.write("%s %s" % entry)
                    cnt += 1
            s.write(");")
            statements.append(s.getvalue())
            s.close()

        nameSIO = StringIO.StringIO()
        valueSIO = StringIO.StringIO()
        for i, column_name in enumerate(input_column_names):
            if i > 0:
                nameSIO.write(", ")
                valueSIO.write(", ")
            nameSIO.write(column_name)
            column_type = local_column_types[column_name]
            if column_type.startswith("TEXT"):
                valueSIO.write("'%s'" % kwargs[column_name])
            elif column_type.startswith("INTEGER"):
                valueSIO.write(str(kwargs[column_name]))
            else:
                raise RuntimeError("Data-type '%s' needs handling" % column_type)

        s = StringIO.StringIO()
        s.write("INSERT INTO %s (%s) VALUES (%s)" % (table_name, nameSIO.getvalue(), valueSIO.getvalue()))
        statements.append(s.getvalue())
        s.close()
    return cb

def run():
    conn = sqlite3.connect(DATABASE_FILENAME)

    # Pass 1: Parse HTML pages and extract data.
    for (table_name, func) in (
            ("conditions", parse_conditions),
            ("special_abilities", parse_special_abilities),
            ("abilities", parse_abilities),
            ("abilities_table", parse_abilities_table),
        ):
        statements = []
        cb = create_callback(table_name, statements)
        func(cb)

        c = conn.cursor()
        sys.stdout.write("%s %d [" % (table_name, len(statements)))
        for s in statements:
            sys.stdout.write(".")
            c.execute(s)
        sys.stdout.write("]"+ os.linesep)

        conn.commit()
        c.close()

    # Pass 2: Inject hard-coded data.


if __name__ == "__main__":
    current_path = sys.path[0]
    html_path = os.path.join(current_path, HTML_DIR_NAME)

    run()

    # Useful if run on Windows within explorer by double-clicking on the BAT
    # script, and you want the window to stay open so you can inspect output.
    raw_input("Press enter to continue..")
