# Python scripts for working with the DND35 OGL SRD

## Support

You can email me at:

 richard.m.tew@gmail.com

If you wish to generally support or encourage the development of this tool, or sponsor the development of specific features, [Paypal donations](http://disinterest.org/donate.html) will be used for that purpose.  For those who are serious about sponsoring development of a specific feature it is best to discuss it with me at my email address first.

## Goal

The goal of these scripts is to provide people who wish to programmatically base their computer game on the SRD data, to do so through the availability of an SQLite database.  On one hand, it provides a script to extend the data in the source SQLite database.  And on the other hand, it provides a simple script to allow the user to introspect and examine the information in the database.

## Features

* Facilitates the availability of a database containing DND35 SRD data.
* Facilitates examination of data contained in the given database.

## Licensing

All files that comprise this are released under the GPLv3 license.

## Installation

The only installation you need to do, is to ensure the following prerequisites are installed on your computer, and in the correct locations.

1. Download and install [Python 2.7](http://python.org/download/) for your platform.
2. Download and install [Beautiful Soup 4](http://pypi.python.org/pypi/beautifulsoup4/4.1.3) extension module for Python 2.7 on your platform.
3. Download and extract the dnd35.sqlite database from [andargor.com](http://www.andargor.com/).
4. Download and extract the HTML files from [OpenSRD](http://sourceforge.net/projects/opensrd) directly into a "SRD-html" subdirectory.

## Usage

With the prerequisites installed, and with the source code that accompanies this file on hand, you should be able to run pysrd.

1. ./run-parse-html.sh
2. ./run-webserver.sh
