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

## Policy Overrides

Policy overrides is an **advanced** feature that allows an operator to override
the default policy of an OpenStack service. The policies that the service
supports, the defaults it implements in its code, and the defaults that a charm
may include should all be clearly understood before proceeding.

> **Caution**: It is possible to break the system (for tenants and other
  services) if policies are incorrectly applied to the service.

Policy statements are placed in a YAML file. This file (or files) is then (ZIP)
compressed into a single file and used as an application resource. The override
is then enabled via a Boolean charm option.

Here are the essential commands (filenames are arbitrary):

    zip overrides.zip override-file.yaml
    juju attach-resource gnocchi policyd-override=overrides.zip
    juju config gnocchi use-policyd-override=true

See appendix [Policy Overrides][cdg-appendix-n] in the [OpenStack Charms
Deployment Guide][cdg] for a thorough treatment of this feature.

<!-- LINKS -->

[cdg]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide
[cdg-appendix-n]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/latest/app-policy-overrides.html
