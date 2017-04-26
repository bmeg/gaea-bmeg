#!/usr/bin/env python

import argparse
import sys
import re
import xml.sax
import json
import logging
import gzip
from ftplib import FTP
from bmeg.nlp_pb2 import Pubmed
from google.protobuf import json_format

reWord = re.compile(r'\w')
reSpace = re.compile(r'\s')

def message_to_json(message):
    msg = json_format.MessageToDict(message)
    #msg['#label'] = message.DESCRIPTOR.name
    return json.dumps(msg)


def ignore(e, v, attrs, **kwds):
    return None

def create_list(e, v, attrs):
    return [v]

def string_pass(e, v, attrs):
    return v

def pass_data(e, v, attrs, **kwds):
    return kwds

def create_dict_list(e, v, attrs, **kwds):
    return [kwds]

def debug_emit(e, v, attrs, **kwds):
    print json.dumps(kwds)

def ignore(k,v, attrs,**kwds):
    return None

def date_extract(e,v, attrs,**kwds):
    return "%s-%s-%s" % (kwds['Year'], kwds['Month'], kwds['Day'])

def emit_pubmed(e,v,attrs, **kwds):
    #print kwds
    out = Pubmed()
    out.pmid = kwds['MedlineCitation']['PMID']
    out.title = kwds['MedlineCitation']['Article']['ArticleTitle']
    if 'Abstract' in kwds['MedlineCitation']['Article']:
        out.abstract = kwds['MedlineCitation']['Article']['Abstract']['AbstractText']
    out.date = kwds['MedlineCitation']['DateCreated']
    print message_to_json(out)


f_map = [
    (['PubmedArticleSet','PubmedArticle'], None, emit_pubmed),

    (['PubmedArticleSet','PubmedArticle','MedlineCitation', 'PMID'], None, string_pass),

    (['PubmedArticleSet','PubmedArticle','MedlineCitation','DateCreated','*'], None, string_pass),
    (['PubmedArticleSet','PubmedArticle','MedlineCitation','DateCreated'], None, date_extract),

    (['PubmedArticleSet','PubmedArticle','MedlineCitation','DateCompleted','*'], None, string_pass),
    (['PubmedArticleSet','PubmedArticle','MedlineCitation','DateCompleted'], None, date_extract),

    (['PubmedArticleSet','PubmedArticle','MedlineCitation','DateRevised','*'], None, string_pass),
    (['PubmedArticleSet','PubmedArticle','MedlineCitation','DateRevised'], None, date_extract),

    (['PubmedArticleSet','PubmedArticle','MedlineCitation'], None, pass_data),

    (['PubmedArticleSet','PubmedArticle','MedlineCitation','Article'], None, pass_data),

    (['PubmedArticleSet','PubmedArticle','MedlineCitation','Article','ArticleTitle'], None, string_pass),
    (['PubmedArticleSet','PubmedArticle','MedlineCitation','Article','Abstract','AbstractText'], None, string_pass),
    (['PubmedArticleSet','PubmedArticle','MedlineCitation','Article','Abstract'], None, pass_data),

]

class StackLevel:
    def __init__(self, name, attrs):
        self.data = {}
        self.name = name
        self.has_children = False
        self.attrs = attrs

def stack_match(query, elem):
    match = True
    if len(query) != len(elem):
        return False
    for q, e in zip(query, elem):
        if isinstance(q, list):
            if e not in q:
                return False
        else:
            if q != "*" and q != e:
                return False
    return True

NOT_FOUND = set()

class PubMedHandler(xml.sax.ContentHandler):
    def __init__(self, record_write):
        xml.sax.ContentHandler.__init__(self)
        self.record_write = record_write
        self.stack = []

    def startElement(self, name, attrs):
        if len(self.stack):
            self.stack[-1].has_children = True
        self.stack.append(StackLevel(name, dict(attrs.items())))
        self.buffer = ""

    def characters(self, text):
        self.buffer += text

    def endElement(self, name):
        found = False
        stack_id = list(i.name for i in self.stack)
        #print stack_id
        level = self.stack.pop()
        for s, out_name, f in f_map:
            if stack_match(s, stack_id):
                found = True
                if out_name is None:
                    out_name = stack_id[-1]
                v = f(self.record_write, self.buffer, level.attrs, **level.data)
                if v is not None:
                    if isinstance(v,list):
                        if out_name in self.stack[-1].data:
                            self.stack[-1].data[out_name].extend(v)
                        else:
                            self.stack[-1].data[out_name] = v
                    elif isinstance(v,dict):
                        if out_name in self.stack[-1].data:
                            self.stack[-1].data[out_name] = dict(self.stack[-1].data, **v)
                        else:
                            self.stack[-1].data[out_name] = v
                    else:
                        self.stack[-1].data[out_name] = v
        if not found:
            n = ",".join(stack_id)
            if n not in NOT_FOUND:
                NOT_FOUND.add(n)
                logging.warning("combiner for %s not found" % (",".join(stack_id)))
        self.buffer = ""

def emit(msg):
    print msg

def parse_pubmed(handle):
    handler = PubMedHandler(emit)
    parser = xml.sax.make_parser()
    parser.setContentHandler(handler)
    parser.parse(handle)

if __name__ =="__main__":
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("-l", action="store_true", default=False)
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()

    if args.l:
        ftp = FTP('ftp.ncbi.nlm.nih.gov')
        ftp.login()
        for i in ftp.nlst("/pubmed/baseline/medline*.xml.gz"):
            print "ftp://ftp.ncbi.nlm.nih.gov%s" % i
    else:
        for path in args.files:
            with gzip.open(path) as handle:
                parse_pubmed(handle)
