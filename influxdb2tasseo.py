#!/usr/bin/env python
# 
# ----------------------------------------------------------------------
""" automatically generate dashboards for tasseo for the lazy one
@pierreaubert """

from os import getenv, path
from sys import exit, argv
from itertools import ifilter
from sets import Set
import requests
import json
import re


# it will generate a dashboard per item
# if the metric match the regexp it will be included in this 
# dashboard
prefs = {
    "main":  {
        'regexp': '^(cpu|df|iostat|load|pages|proc)\.',
        'name': 'network.js'
    },
    "network" : {
        'regexp': '^(ip|tcp|arp|udp|icmp|igmp|ipsec|rip|pfkey)',
        'name': 'network.js'
    },
    "temperature" : {
        'regexp': '^(temperature\.)',
        'name': 'temperature.js'
    },
    "all" : {
        'regexp': '.*',
        'name': 'all.js'
    },
}

influxdb_auth = getenv('INFLUXDB_AUTH') 
influxdb_db_url = getenv('INFLUXDB_URL')
influxdb_user = None
influxdb_pwd = None

if influxdb_auth is None:
    print "INFLUXDB_AUTH is not set"
    exit(-1)
else:
    influxdb_user, influxdb_pwd = influxdb_auth.split(':')
    if influxdb_user is None or influxdb_pwd is None:
        print "INFLUXDB_AUTH is ill formed must be: user:pwd"
        exit(-1)


if influxdb_db_url is None:
    print "INFLUXDB_DB_URL is not set"
    exit(-1)


influxdb_db_url = influxdb_db_url + '/series'


def call_server(query):
    """ call the rest api of influxdb """
    payload = {
        "u": influxdb_user,
        "p": influxdb_pwd,
        "q": query
    }
    r = requests.get(influxdb_db_url, params=payload)
    if r.status_code != requests.codes.ok:
        print 'call to {0} failed!'.format(influxdb_db_url)
    return r.json()


def get_metrics():
    """ get list of all metrics """
    query = 'select * from /.*/ limit 1;'
    text =  call_server(query)
    return [ t['name'] for t in text]


def get_metrics_bounds(metrics):
    """ for each metrics compute lower/higher value """
    bounds = {}
    for m in metrics:
        # print 'debug: ' +  m 
        query = 'select value from {0} limit 100000;'.format(m)
        text =  call_server(query)
        #print text[0]['points']
        datas = [ d[2] for d in text[0]['points'] ]
        # if no data, just drop the metric
        if datas is not None and len(datas)>0:
            m_min = min(datas)
            m_max = max(datas)
            if m_min < m_max:
                bounds[m] = {
                    'min': m_min,
                    'max': m_max
                } 
    return bounds


def compute_warning(imin, imax):
    # normalize between 0, 1, >0
    if min >= 0 and max <= 100:
        return 50
    else:
        return imax/2.0


def compute_critical(imin, imax):
    # normalize between 0, 1, >0
    if min >= 0 and max <= 100:
        return 90
    else:
        return imax*0.9


def print_metrics(metrics, bounds):
    """ generate a dashboard for tasseo """
    for m in metrics:
        # if we have bounds
        if m in bounds:
            imin = float(bounds[m]['min'])
            imax = float(bounds[m]['max'])
            iwar = compute_warning(imin, imax)
            icri = compute_critical(imin, imax)
            # print in each dashboard
            for p in prefs:
                # if it match the regexp
                if re.match( prefs[p]['regexp'], m):
                    fd = prefs[p]['fd']
                    fd.write('  {\n')
                    fd.write('     "series": "{0}",\n'.format(m))
                    fd.write('     "target": "{0}",\n'.format(m))
                    fd.write('     "warning": {0},\n'.format(iwar))
                    fd.write('     "critical": {0},\n'.format(icri))
                    fd.write('  },\n')
                    

def uniq(iterable):
    # fast uniq
    m = Set()
    m_add = set.add
    return ifilter(lambda x: not (m.__contains__(x) or m_add(x)), iterable)


def uniq2(l):
    # slow uniq
    m = Set()
    for i in l:
        k = i.split('.')
        m.add(k[0])
    return list(m)

def begin_file():
    for dashboard in prefs:
        fd = open( 'imac-{0}.js'.format(dashboard), 'w' )
        prefs[dashboard]['fd'] = fd
        fd.write( 'var metrics=[\n' )

def end_file():
    for dashboard in prefs:
        fd = prefs[dashboard]['fd']
        fd.write( '];\n\n' )
        prefs[dashboard]['fd'].close()        

def main(argv):
    begin_file()
    metrics = get_metrics()    
    metrics = sorted(metrics)
    # aggregate = uniq2(metrics)
    bounds = get_metrics_bounds(metrics)
    print_metrics(metrics, bounds)
    end_file()
    return 0

if __name__ == '__main__':
    exit(main(argv))
