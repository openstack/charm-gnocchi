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

Gnocchi then needs to be initialized with the current ceilometer data:

    juju run-action <ceilometer unit leader> ceilometer-upgrade

# Usage with S3 storage backend

> **Note**: S3 storage support for Gnocchi is available starting with OpenStack
  Stein.

Gnocchi is configured to be deployed by default with Ceph, however,
it can also connect to an S3 storage backend. To configure Gnocchi with S3,
configuration options (`storage-backend`, `s3-region-name`, `s3-endpoint-url`,
`s3-access-key-id` and `s3-secret-access-key`) must be provided.
Please take a look at `config.yaml` for more details.