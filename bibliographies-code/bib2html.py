#!/usr/bin/env python
# coding: latin1

"""
The script processes the BIB database and generates html pages for https://github.com/webis-de/webis-de.github.io
using a jinja2 template and lxml.html.builder.

usage: bib2html.py [-h] --input-path INPUT_PATH --output-path OUTPUT_PATH

arguments:
  -h, --help            show this help message and exit
  --input-path INPUT_PATH
                        Input path to CVS folder containing Webis web-database *.bib files (data-webis.bib, etc.)
  --output-path OUTPUT_PATH
                        Output path where generated HTML files should be exported (e.g. webis-de.github.io repository)

"""

import argparse
import base64
import re
import time
from html import escape
import logging
import io
import json
import os
import pathlib
import sys
import random
import traceback
from collections import OrderedDict
from datetime import datetime

import jinja2
import lxml.html
import pybtex.errors
import requests
from jinja2 import Template, Environment, BaseLoader, FileSystemLoader, StrictUndefined
from lxml import etree as et
from lxml.html.builder import *

from pybtex import textutils
from pybtex.database.input.bibtex import month_names
from pybtex.bibtex.utils import split_name_list, split_tex_string
from pybtex.database import Person, Entry
from pybtex.richtext import Text, BaseText
from pybtex.database.input.bibtex import DuplicateField
from pybtex.py3compat import fix_unicode_literals_in_doctest

script_dir = os.path.dirname(os.path.abspath(__file__))
# sys.path.insert(0, script_dir + '/pybtex.zip')
from pybtex.database.input import bibtex

bib2html_logger = logging.getLogger(__name__)
bib2html_logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
bib2html_logger.addHandler(handler)


github_webis = {
    'webis': {
        'directory': 'publications',
        'domain': 'https://webis.de',
        'repo': 'downloads',
        'username': 'webis-de'
    },
    'pan': {
        'directory': 'publications',
        'domain': 'https://pan.webis.de',
        'repo': 'downloads',
        'username': 'pan-webis-de'
    },
    'theses': {
        'directory': 'theses',
        'domain': 'https://webis.de',
        'repo': 'downloads',
        'username': 'webis-de'
    },
    'touche': {
        'directory': 'publications',
        'domain': 'https://touche.webis.de',
        'repo': 'downloads',
        'username': 'touche-webis-de'
    }
}

max_editor_names = 4


class WebisBibParser(bibtex.Parser):
    def __init__(self, *args, bib_type="other", **kwargs):
        """
        :param bib_type: "data" or "other"
        """
        super(WebisBibParser, self).__init__(*args, **kwargs)
        self.bib_type = bib_type

    def process_entry(self, entry_type, key, fields):
        entry = Entry(entry_type)

        if key is None:
            key = 'unnamed-%i' % self.unnamed_entry_counter
            self.unnamed_entry_counter += 1

        seen_fields = set()
        for field_name, field_value_list in fields:
            if field_name.lower() in seen_fields:
                self.handle_error(DuplicateField(key, field_name))
                continue

            field_value = textutils.normalize_whitespace(self.flatten_value_list(field_value_list))
            if field_name in self.person_fields:
                for name in split_name_list_comma(field_value) if self.bib_type == 'data' else split_name_list(
                        field_value):
                    entry.add_person(Person(name), field_name)
            else:
                entry.fields[field_name] = field_value
            seen_fields.add(field_name.lower())
        if key in self.data.entries:
            #TODO: Find another solution this is just a hack to deal with duplicates
            key = key + "-" + str(random.randrange(0,1000,2))
        self.data.add_entry(key, entry)


def split_name_list_comma(string):
    return split_tex_string(string, " *[,]{1} *")


def get_person_name(person, format="latex"):
    return f"{' '.join(n.render_as(format) for n in person.rich_first_names)} " \
           f"{' '.join(n.render_as(format) for n in person.rich_middle_names)} " \
           f"{' '.join(n.render_as(format) for n in person.rich_last_names)}"

def format_persons(persons, format="latex", max_persons=9999):
    persons_str = ""
    if format == "latex":
        persons_str = " and ".join(
            f"{' '.join(n for n in p.bibtex_first_names)} {' '.join(n for n in p.last_names)}" for p in persons)
    else:
        if len(persons) == 1:
            persons_str = get_person_name(persons[0], format)
        elif len(persons) == 2:
            persons_str = get_person_name(persons[0], format) + " and " + get_person_name(persons[1], format)
        elif len(persons) >= 2 and len(persons) <= max_persons:
            persons_str = ", ".join(get_person_name(p, format) for p in persons[:-1]) + ", and " + get_person_name(persons[-1], format)
        elif len(persons) > max_persons:
            persons_str = get_person_name(persons[0], format) + " et al."

    return persons_str


def get_raw_bib_entry(item):
    month_names_inv = {v: k for k, v in month_names.items()}
    fields_string = ""
    for key, value in sorted(item.fields.items()):
        if key in [
                    'annote',
                    'arxivpassword',
                    'arxivurl',
                    'awardurl',
                    'bibid',
                    'clef-working-notesurl',
                    'codeurl',
                    'data_author',
                    'data_editor',
                    'dataurl',
                    'demourl',
                    'ecir-invited-paperurl',
                    'eventurl',
                    'keywords',
                    'mentor',
                    'options',
                    'request',
                    'researchurl',
                    'videourl',
                    'wikipediaurl',
                    'authorkeys', 'category', 'publicationsquery'
                  ] or not value or value == "-":
            continue
        spaces = " " * (25 - len(key))
        if key == 'month':
            value = month_names_inv.get(value, 'jan')
        elif key == 'author' or key == 'people':
            value = f"{{{format_persons(item.persons.get('author', []), 'latex')}}}"
        elif key == 'editor':
            value = f"{{{format_persons(item.persons.get('editor', []), 'latex')}}}"
        elif key not in ['articleno', 'number', 'numpages', 'pages', 'volume', 'year'] or not value.isnumeric():
            value = f"{{{value}}}"
        fields_string += f"  {key} ={spaces}{value},\n"
    return f"""@{item.original_type}{{{item.key},\n{fields_string[:-2]}\n}}"""


def request_github(username, repo):
    # authorization = f'token {access_token}'
    headers = {
        "Accept": "application/vnd.github.v3+json",
        # "Authorization": authorization,
    }

    url_api_repos = "https://api.github.com/repos"
    url_api_param_tree = "git/trees/HEAD?recursive=1"
    url_repo_base = f"{url_api_repos}/{username}/{repo}"
    url_repo_tree = f"{url_repo_base}/{url_api_param_tree}"

    response = requests.get(url_repo_tree, headers=headers)
    response.raise_for_status()
    return json.loads(response.content.decode('utf-8'))


def get_downloads_url(path):
    return f"downloads/{path}"

def get_existing_hrefs(username, repo, directory):
    existing_hrefs = dict()
    key_regex = re.compile(r'\/([a-z_\-0-9]*)\..*$')
    for i in range(2):  # retry in case of a connection issue
        try:
            response = request_github(username=username, repo=repo)
            existing_hrefs['publications'] = {key_regex.findall(x['path'])[0]: get_downloads_url(x['path']) for x in
                                              response['tree'] if x['path'].startswith(directory + '/papers/')}
            existing_hrefs['posters'] = {key_regex.findall(x['path'])[0]: get_downloads_url(x['path']) for x in
                                         response['tree'] if x['path'].startswith(directory + '/posters/')}
            existing_hrefs['slides'] = {key_regex.findall(x['path'])[0]: get_downloads_url(x['path']) for x in
                                        response['tree'] if x['path'].startswith(directory + '/slides/')}
        except Exception as e:
            print(e)
            bib2html_logger.error("Error occurred while requesting Webis resources data from GitHub.",
                                  exc_info=True)
            traceback.print_exc()
            sys.exit(1)
        break

    return existing_hrefs


class Bib2Html:
    universities = {'weimar': "Bauhaus-Universit�t Weimar"}

    data_categories = {'released-webis-corpora': "Released Webis Corpora",
                       'pan-corpora': "PAN Corpora",
                       'touche-corpora': "Touch� Corpora",
                       'internal-webis-corpora': "Internal Webis Corpora",
                       'affiliated-corpora': "Affiliated Corpora",
                       'other-corpora': "Other Corpora"}
    
    people_categories = {'secretaries': 'Secretary',
                         'assistants': 'Assistants',
                         'former-assistants': 'Former Assistant',
                         'visiting-researchers': 'Visiting Researchers',
                         'external-phds': 'External PhD',
                         'head': 'Head',
                         'student-assistants': 'student-assistants'}

    dataset_page_template_filename = script_dir + "/templates/dataset_page.html.jinja2"
    data_table_template_filename = script_dir + "/templates/data_table.html.jinja2"
    bib_list_template_filename = script_dir + "/templates/publications.html.jinja2"
    people_template_filename = script_dir + "/templates/people.html.jinja2"

    def __init__(self, input_path, output_path):
        self.input_path = input_path
        self.output_path = output_path

        self.log_capture_string = io.StringIO()
        self.ch = logging.StreamHandler(self.log_capture_string)
        self.ch.setLevel(logging.INFO)
        bib2html_logger.addHandler(self.ch)

        self.bib_data_people = self.load_bib_file("webis-people.bib")
        self.html_files_count = 0

        templateLoader = jinja2.FileSystemLoader(searchpath=script_dir + "/templates")
        # templateEnv = jinja2.Environment(loader=templateLoader, undefined=StrictUndefined) # StrictUndefined for required fields in templates
        self.templateEnv = jinja2.Environment(loader=templateLoader)

    def __del__(self):
        bib2html_logger.removeHandler(self.ch)

    def get_table(self, category_id, webis_people, output_path):
        """

        :param category_id:
        :param bib_data:
        :return:
        """
        with open(self.data_table_template_filename, 'r') as file:
            data_table_template = file.read()

        t = Template(data_table_template)
        output = t.render(category_id=category_id, category_name=self.data_categories[category_id])

        table = lxml.html.fragment_fromstring(output)
        for i, item in enumerate(webis_people):
            row = self.get_row(item.key, item, output_path)
            table.find("tbody").append(row)

        et.indent(table, space="\t", level=0)

        return et.tostring(table, pretty_print=True).decode("iso-8859-1").replace("CLASS", "class")

    def create_people_page(self, category_id, webis_people, output_path):
        """

        :param category_id:
        :param webis-people:
        :return:
        """
        with open(self.people_template_filename, 'r') as file:
            people_template = file.read()

        t = Template(people_template)
        output = t.render(category_id=category_id, category_name=self.people_categories[category_id])

        entry = lxml.html.fragment_fromstring(output)
        for i, item in enumerate(webis_people):
            row = self.get_row(item.key, item, output_path)
            entry.find("div").append(row)

        et.indent(entry, space="\t", level=0)

        return et.tostring(entry, pretty_print=True).decode("iso-8859-1").replace("CLASS", "class")




    def get_jsonld(self, item):
        """ todo: switch to PyLD"""
        def distribution(item):
            dist_list = []
            if self.has_value(item, 'browserurl'):
                dist_list.append({"@type": "DataDownload", "contentUrl": item.fields['browserurl']})
            if self.has_value(item, 'zenodourl'):
                dist_list.append({"@type": "DataDownload", "contentUrl": item.fields['zenodourl']})
            if self.has_value(item, 'googleurl'):
                dist_list.append({"@type": "DataDownload", "contentUrl": item.fields['googleurl']})
            if self.has_value(item, 'internetarchiveurl'):
                dist_list.append({"@type": "DataDownload", "contentUrl": item.fields['internetarchiveurl']})
            return dist_list

        doc = {
            "@context": "http://schema.org/",
            "@type": "Dataset",
            "name": item.fields['title'],
            "description": item.fields['synopsishtml'],
            "url": "https://webis.de/data/" + item.fields['title'],
            "sameAs": item.fields.get('zenodourl', '-'),
            "license": "https://creativecommons.org/licenses/by/4.0/deed.en",
            "keywords": [s.strip() for s in item.fields['keywords'].split(',')],
            "datePublished": item.fields.get('year', '-'),
            "creator": None,
            "includedInDataCatalog": {
                "@type": "DataCatalog",
                "name": "Webis Data Catalog",
                "url": "https://webis.de/data/"
            },
            "distribution": [distribution(item)]
        }

        creator = [
            {
                "@type": "Organization",
                "url": "https://webis.de/",
                "name": "The Web Technology & Information Systems Network",
                "alternateName": "Webis Group"
            }
        ]

        for p in item.fields['people']:
            person = {
                '@type': "Person",
                '@id': p.get('orcid', ""),
                'name': p['fullname'],
                "url": p.get('url', ""),
                "affiliation": p.get('institution', "")
            }

            creator.append(person)

        doc['creator'] = creator

        return json.dumps(doc, sort_keys=False, indent=4, separators=(',', ': '))

    @staticmethod
    def has_value(item, field):
        value = item.fields.get(field, "-")
        return value.strip() not in ["-", ""]

    def get_row(self, key, item, output_path):
        """Generate row for each data table entry.

        :param key:
        :param item:
        :return:
        """

        def ATTR(key, value):
            return {key: value}

        dataset_url = ""
        if self.has_value(item, 'synopsishtml'):
            dataset_page_filename = self.create_dataset_page(key, item, output_path)
            dataset_url = "data/" + dataset_page_filename
            self.html_files_count += 1
        elif self.has_value(item, 'url'):
            dataset_url = item.fields['url']

        self.fields_to_text(item)
        row = TR(
            TD(id=key),
            TD(A(item.fields['title'], href=dataset_url)) if dataset_url else TD(item.fields['title']),
            TD(item.fields['publisher']),
            TD(item.fields['year'], CLASS="uk-text-center"),
            TD(item.fields['sizebytescompressed'], CLASS="numeric"),
            TD(item.fields['sizeunits'], CLASS="numeric"),
            TD(item.fields['sizeunittype']),
            TD(item.fields['tasks']),
            TD(
                A(I((""), ATTR("aria-hidden", "true"), ATTR("class", "fa fa-eye uk-text-muted")), ATTR("class", "uk-link-reset"), title="Browser",
                  href=item.fields['browserurl']) if self.has_value(item, 'browserurl') else "",
                A(IMG(src="data/img/zenodo-icon.png", alt="Zenodo"), ATTR("class", "uk-link-reset"), title="Download: Zenodo",
                  href=item.fields['zenodourl']) if self.has_value(item, 'zenodourl') else "",
                A(IMG(src="data/img/google-icon.png", alt="Google Dataset Search"), ATTR("class", "uk-link-reset"), title="Indexed: Google",
                  href=item.fields['googleurl']) if self.has_value(item, 'googleurl') else "",
                A(IMG(src="data/img/ia-icon.png", alt="Internet Archive"), ATTR("class", "uk-link-reset"), title="Internet Archive",
                  href=item.fields['internetarchiveurl']) if self.has_value(item, 'internetarchiveurl') else "",
                CLASS="uk-text-right"
            )
        )

        # print(et.tostring(row, pretty_print=False, with_tail=False))
        return row

    def create_dataset_page(self, key, item, output_path):
        """

        :param key:
        :param item:
        :return:
        """
        with open(self.dataset_page_template_filename, 'r') as file:
            dataset_page_template = file.read()

        dataset_page_filename = key + ".html"

        item.fields['people'] = self.get_people(item)
        item.fields['synopsis'] = re.sub('<[^>]+>', '', item.fields['synopsishtml']).strip()
        item.fields['raw'] = get_raw_bib_entry(item)
        item.fields['jsonld'] = self.get_jsonld(item)

        t = Template(dataset_page_template)
        output = t.render(key=key, item=item, has_value=self.has_value)

        output_file_path = pathlib.Path(self.output_path + "/" + output_path + "/data/" + dataset_page_filename)
        output_file_path.parent.mkdir(exist_ok=True, parents=True)
        with open(output_file_path, 'w') as f:
            f.write(output)

        return dataset_page_filename

    def get_href_if_exists(self, domain, resource_type, item):
        href = self.existing_hrefs[resource_type].get(item.key.replace(':', '_'), False)
        if href:
            item.fields[resource_type + '_href'] = domain + "/" + href
        return item

    def get_people(self, item):
        """

        :param item:
        :return:
        """
        authornames = []
        for p in item.fields['authorkeys'].split(", "):
            if p[0] == '"':
                fullname = p.replace('"', '').replace('"', '')
                authornames.append({'fullname': fullname})
            else:
                entry = self.bib_data_people.entries.get(p, None)
                if entry:
                    fullname = f"{entry.fields['namefirst']} {entry.fields['namelast']}".translate(
                        str.maketrans('', '', "{}"))
                    institution = entry.fields.get('institution', None)
                    link = "https://www.uni-weimar.de/en/media/chairs/computer-science-department/webis/people/#" + p
                    # todo: clarify case when to use personalurl
                    # if institution and institution == self.universities['weimar']:
                    #     link = "https://www.uni-weimar.de/en/media/chairs/computer-science-department/webis/people/#" \
                    #            + p
                    # else:
                    #     link = entry.fields.get('personalurl', "")
                    authornames.append({'fullname': fullname,
                                        'url': link,
                                        'institution': institution,
                                        'orcid': entry.fields.get('orcid', "")})
        return authornames

    def load_bib_file(self, filename, bib_type="other"):
        return WebisBibParser(encoding='iso-8859-1', bib_type=bib_type).parse_file(self.input_path + filename)

    def format_stacktrace(self, bib_filename, exception):
        traceback_str = ' '.join(traceback.format_tb(exception.__traceback__)) + str(exception)
        if __name__ != '__main__':
            message = f"\n- Error in: {bib_filename} [please check bib files, see <a download='bib2html_error.txt' href='data:text/plain;base64,{base64.b64encode(traceback_str.encode()).decode()}'>stacktrace</a>]"
        else:
            message = f"\n- Error in: {bib_filename} [please check bib files, see stracktrace: {str(traceback_str)}]"
        return message

    def data(self, bib_files={}, output_path=""):
        """
            1. iterate over bib files
            2. for data bib files:
                - group bibitems by category
                - generate table per category
            3. for bibitems with synopsis
                - generate separate html page
        :param:
        :return:
        """
        bib2html_logger.info("\n2. Update data.")

        bib_data = dict()
        files_parsed_string = ""
        for k, bib_filename in bib_files.items():
            try:
                bib_data[k] = self.load_bib_file(bib_filename, bib_type="data")
                files_parsed_string += f"\n- {bib_filename}"
            except Exception as e:
                files_parsed_string += self.format_stacktrace(bib_filename, e)
                continue
        bib2html_logger.info("""\nBib files parsed: """ + files_parsed_string)

        # Create data tables
        output = ""
        grouped = {}
        self.html_files_count += 1
        for key, item in bib_data['data-webis'].entries.items():
            if not item.fields['category'] in grouped:
                grouped[item.fields['category']] = []
            grouped[item.fields['category']].append(item)
        for category in self.data_categories.keys():
            if category in grouped:
                entries = grouped[category]
                entries = sorted(entries, key=lambda x: x.fields['title'].lower())
                output += self.get_table(category, entries, output_path)

        bib_data_other_sorted = sorted(bib_data['data-other'].entries.values(), key=lambda x: x.fields['title'].lower())
        output += self.get_table("other-corpora", bib_data_other_sorted, output_path)

        output_file_path = pathlib.Path(self.output_path + "/" + output_path + f"/_includes/bib-data.html")
        output_file_path.parent.mkdir(exist_ok=True, parents=True)
        with open(output_file_path, 'w') as outputfile:
            outputfile.write("{% raw %}\n" + output + "\n{% endraw %}")


    def publications(self, bib_files={}, output_path={}):
        """
        - group bib-entries by year
        :return:
        """
        bib2html_logger.info("\n1. Update publications.")
        with open(self.bib_list_template_filename, 'r') as file:
            bib_list_template = file.read()

        bib_publications = dict()
        files_parsed_string = ""
        for k, bib_filename in bib_files.items():
            try:
                bib_publications[k] = self.load_bib_file(bib_filename)
                files_parsed_string += f"\n- {bib_filename}"
            except Exception as e:
                files_parsed_string += self.format_stacktrace(bib_filename, e)
                continue
        bib2html_logger.info("""\nBib files parsed: """ + files_parsed_string)

        files_list_str = ""
        for output_publications_filename, bib_publications in bib_publications.items():
            website = output_publications_filename.split("-")[1]
            self.existing_hrefs = get_existing_hrefs(github_webis[website]['username'], github_webis[website]['repo'], github_webis[website]['directory'])
            grouped = {}
            for item in bib_publications.entries.values():
                if 'options' in item.fields and 'skipbib=true' in item.fields['options']:
                    continue
                if item.key.startswith("collection-"):
                    continue
                if not item.fields['year'] in grouped:
                    grouped[item.fields['year']] = []
                item.fields['author'] = format_persons(item.persons.get('author', []), "text")
                item.fields['data_author'] = ",".join([get_person_name(person, "text") for person in item.persons.get('author', [])])
                if 'editor' in item.persons:
                    max_names = max_editor_names
                    if item.type in ["incollection", "proceedings"]:
                        max_names = 9999999
                    item.fields['editor'] = format_persons(item.persons.get('editor', []), "text", max_names)
                    item.fields['data_editor'] = ",".join([get_person_name(person, "text") for person in item.persons.get('editor', [])])
                item.fields['bibid'] = item.key.replace(":", "_")
                item.fields['raw'] = get_raw_bib_entry(item)
                item.fields['title'] = re.sub("\\\\sc ", "", item.fields['title'].translate(str.maketrans('', '', '{}')))
                item = self.get_href_if_exists(github_webis[website]['domain'], "publications", item)
                item = self.get_href_if_exists(github_webis[website]['domain'], "posters", item)
                item = self.get_href_if_exists(github_webis[website]['domain'], "slides", item)

                artifacts = [re.sub("posters", "poster", re.sub("_href$", "", re.sub("url$", "", field_name))) for field_name in item.fields if (field_name in ["doi", "posters_href", "slides_href"] or (field_name.endswith("url") and field_name != "url")) and item.fields[field_name] != ""]
                if len(artifacts) > 0:
                    item.fields['artifacts'] = ",".join(artifacts)

                grouped[item.fields['year']].insert(0, item)
                self.fields_to_text(item)

            self.sort_publication_items(grouped)

            t = self.templateEnv.get_template("publications.html.jinja2")

            try:

                output = t.render(bib_entries=OrderedDict(sorted(grouped.items(), reverse=True)).items())
            except jinja2.exceptions.UndefinedError as e:
                bib2html_logger.error("Error in: " + str(e), exc_info=True)
                traceback.print_exc()
                continue

            output_file_path = pathlib.Path(self.output_path + "/" + output_path[output_publications_filename] + f"/_includes/{output_publications_filename}.html")
            output_file_path.parent.mkdir(exist_ok=True, parents=True)
            with open(output_file_path, 'w') as outputfile:
                outputfile.write("{% raw %}\n" + output + "\n{% endraw %}")

            files_list_str += f"\n- {output_publications_filename}.html"
        bib2html_logger.info(f"\nWeb pages generated:{files_list_str}")

    def lecturenotes(self, bib_files={}):
        """
        - parse `webis-lecturenotes.bib` file structure
        - generate `lecturenotes.html` template
        - generate `course-map.html` template
        - lecturenotes/browser
        :return:
        """
        pass

    def iranthology(self, bib_files={}, output_path={}):
        """
        - group bib-entries by year
        :return:
        """
        start = time.time()
        bib2html_logger.info("\n1. Update iranthology.")
        with open(self.bib_list_template_filename, 'r') as file:
            bib_list_template = file.read()

        bib_publications = dict()
        files_parsed_string = ""
        for k, bib_filename in bib_files.items():
            try:
                bib_publications[k] = self.load_bib_file(bib_filename)
                files_parsed_string += f"\n- {bib_filename}"
            except Exception as e:
                files_parsed_string += self.format_stacktrace(bib_filename, e)
                continue
        bib2html_logger.info("""\nBib files parsed: """ + files_parsed_string)
        bib2html_logger.info(F"\nParsing took: {time.time()-start}" )

        files_list_str = ""
        for output_publications_filename, bib_publications in bib_publications.items():
            website = output_publications_filename.split("-")[1]
            #self.existing_hrefs = get_existing_hrefs(github_webis[website]['username'], github_webis[website]['repo'], github_webis[website]['directory'])
            grouped = {}
            for item in bib_publications.entries.values():
                if 'options' in item.fields and 'skipbib=true' in item.fields['options']:
                    continue
                if item.key.startswith("collection-"):
                    continue
                if not item.fields['year'] in grouped:
                    grouped[item.fields['year']] = []
                item.fields['author'] = format_persons(item.persons.get('author', []), "text")
                item.fields['data_author'] = ",".join([get_person_name(person, "text") for person in item.persons.get('author', [])])
                if 'editor' in item.persons:
                    max_names = max_editor_names
                    if item.type in ["incollection", "proceedings"]:
                        max_names = 9999999
                    item.fields['editor'] = format_persons(item.persons.get('editor', []), "text", max_names)
                    item.fields['data_editor'] = ",".join([get_person_name(person, "text") for person in item.persons.get('editor', [])])
                item.fields['bibid'] = item.key.replace(":", "_")
                item.fields['raw'] = get_raw_bib_entry(item)
                item.fields['title'] = re.sub("\\\\sc ", "", item.fields['title'].translate(str.maketrans('', '', '{}')))
                #item = self.get_href_if_exists(github_webis[website]['domain'], "publications", item)
                #item = self.get_href_if_exists(github_webis[website]['domain'], "posters", item)
                #item = self.get_href_if_exists(github_webis[website]['domain'], "slides", item)

                #artifacts = [re.sub("posters", "poster", re.sub("_href$", "", re.sub("url$", "", field_name))) for field_name in item.fields if (field_name in ["doi", "posters_href", "slides_href"] or (field_name.endswith("url") and field_name != "url")) and item.fields[field_name] != ""]
                #if len(artifacts) > 0:
                #    item.fields['artifacts'] = ",".join(artifacts)

                grouped[item.fields['year']].insert(0, item)
                self.fields_to_text(item)

            self.sort_publication_items(grouped)

            t = self.templateEnv.get_template("publications.html.jinja2")

            try:

                output = t.render(bib_entries=OrderedDict(sorted(grouped.items(), reverse=True)).items())
            except jinja2.exceptions.UndefinedError as e:
                bib2html_logger.error("Error in: " + str(e), exc_info=True)
                traceback.print_exc()
                continue

            output_file_path = pathlib.Path(self.output_path + "/" + output_publications_filename + f"/_includes/{output_publications_filename}.html")
            output_file_path.parent.mkdir(exist_ok=True, parents=True)
            with open(output_file_path, 'w') as outputfile:
                outputfile.write("{% raw %}\n" + output + "\n{% endraw %}")

            files_list_str += f"\n- {output_publications_filename}.html"
        bib2html_logger.info(f"\nWeb pages generated:{files_list_str}")
        bib2html_logger.info(f"\nWeb pages generation took:{time.time() - start}")



    def sort_publication_items(self, grouped):
        for year, entries in grouped.items():
            try:
                grouped[year] = sorted(entries, key=lambda x: (
                    -datetime.strptime(x.fields['month'], "%B").month if 'month' in x.fields and x.fields['month'] else -13,
                    re.sub(r"^([0-9])", r"AAAA\1", x.fields['booktitle'] if 'booktitle' in x.fields and x.fields['booktitle'] else "aaaaaa"),
                    x.fields['bibid']))
            except Exception as e:
                print(e)

    def fields_to_text(self, item):
        try:
            for k, v in item.fields.items():
                if k == "raw" or type(v) is not str:
                    continue
                item.fields[k] = v if "url" in k else str(Text.from_latex(v))
        except Exception as e:
            print(e)
        

    def people(self, bib_files={}, output_path={}):
        
        start = time.time()
        bib_people = dict()
        files_parsed_string = ""
        for k, bib_filename in bib_files.items():
            try:
                bib_people[k] = self.load_bib_file(bib_filename)
                files_parsed_string += f"\n- {bib_filename}"
            except Exception as e:
                files_parsed_string += self.format_stacktrace(bib_filename, e)
                continue
        bib2html_logger.info("""\nBib files parsed: """ + files_parsed_string)
        bib2html_logger.info(F"\nParsing took: {time.time()-start}" )
        
        bib_entries = bib_people['webis-people'].entries

        # Convert the entries to a list of dictionaries
        bib_dicts = [entry.fields for entry in bib_entries.values()]

        # Load the Jinja template
        #template = jinja2.Template(self.people_template_filename)
        t = self.templateEnv.get_template("people.html.jinja2")
        
        output = t.render(peoples=bib_dicts)
        #output = t.render(namelast, nametitle, namelast, email, institution, interests)

        output_file_path = pathlib.Path(self.output_path + "/" + output_path + f"/_includes/people.html")
        output_file_path.parent.mkdir(exist_ok=True, parents=True)
        with open(output_file_path, 'w') as outputfile:
            outputfile.write("{% raw %}\n" + output + "\n{% endraw %}")


        
        

    def execute(self, to_execute=["people"], log_capture_string=None):
        tasks = {'publications': {'func': self.publications,
                                  'files': {'bib-pan': 'pan-publications.bib',
                                            'bib-touche': 'touche-publications.bib',
                                            'bib-webis': 'webis-publications.bib',
                                            'bib-theses': 'webis-theses.bib'},
                                  'output_path': {'bib-pan': 'pan-webis-de',
                                                  'bib-touche': 'touche-webis-de',
                                                  'bib-webis': 'webis-de',
                                                  'bib-theses': 'webis-de'},
                                  },
                 'data': {'func': self.data,
                          'files': {'data-webis': 'webis-data.bib',
                                    'data-other': 'other-data.bib'},
                          'output_path': 'webis-de'
                          },
                 'people': {'func': self.people,
                            'files': {'webis-people': 'webis-people.bib'},
                            'output_path': 'webis-de',
                            },
                 'lecturenotes': {'func': self.lecturenotes,
                                  'files': {'lecturenotes': 'lecturenotes.bib'},
                                  'output_path': 'webis-de',
                                  }
                 }

        for task, task_data in tasks.items():
            if task in to_execute:
                task_data['func'](task_data['files'], task_data['output_path'])

        bib2html_logger.info(f"\nWeb pages generated: {self.html_files_count}")

        if log_capture_string:
            self.log_capture_string = log_capture_string

        return self.log_capture_string.getvalue()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Webis web-database to HTML exporter')
    parser.add_argument('--input-path', '-i', type=str, required=True, dest='input_path',
                        help="Input path to <cvs>/literature/webis-publications folder with bib-files.")
    parser.add_argument('--output-path', '-o', type=str, required=True, dest='output_path',
                        help="Output path to export generated html-files.")
    parser.add_argument('-c', '--create-output-path', action='store_true', help="Create output path.")
    parser.add_argument('-f', '--output-overwrite', action='store_true', help="Overwrite output path.")
    parser.add_argument('-t', '--tasks', type=str, nargs='+', default=["people"],
                        help="Set tasks (all by default).")
    args = parser.parse_args()
    bib2html_logger.info("bib2html.py script called with arguments: %s" % vars(args))

    input_path = pathlib.Path(args.input_path)
    output_path = pathlib.Path(args.output_path)
    if not input_path.exists() or not output_path.exists():
        if args.create_output_path:
            output_path.mkdir()
        else:
            sys.exit(
                f"Path does not exist: {[str(p.absolute()) for p in [input_path, output_path] if not p.exists()]}, "
                f"use -c option to create output directory.")
    if any(output_path.iterdir()) and not args.output_overwrite:
        sys.exit(f"Directory is not empty: {output_path.absolute()}, use -f option to overwrite.")
    bib2html = Bib2Html(args.input_path, args.output_path)

    # tasks to be executed
    bib2html.execute(args.tasks)
