# Overview

Gnocchi is an open-source, multi-tenant timeseries, metrics and resources
database. It provides an HTTP REST interface to create and manipulate the
data. It is designed to store metrics at a very large scale while providing
access to metrics and resources information and history.

# Usage

Gnocchi is typically deployed as part of an OpenStack cloud, providing storage
for Ceilometer, the telemetry collection service; To deploy Gnocchi to an
existing OpenStack cloud (which includes ceilometer):

    juju deploy gnocchi
    juju deploy memcached
    juju add-relation gnocchi mysql
    juju add-relation gnocchi memcached
    juju add-relation gnocchi keystone
    juju add-relation gnocchi ceph-mon
    juju add-relation gnocchi ceilometer

After re-configuration the Ceilometer API will be disabled - the Gnocchi REST
API should be used to query information on resource, metrics and associated
measures.