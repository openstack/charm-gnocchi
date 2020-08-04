# Overview

[Gnocchi][gnocchi-upstream] is an open-source, multi-tenant timeseries,
metrics, and resources database. It provides an HTTP REST interface to create
and manipulate the data. It is designed to store metrics at a very large scale
while providing access to metrics and resources information and history.

# Usage

## Configuration

See file `config.yaml` for the full list of configuration options, along with
their descriptions and default values. See the [Juju
documentation][juju-docs-config-apps] for details on configuring applications.

## Deployment

Gnocchi is typically deployed as part of an OpenStack cloud, providing storage
for Ceilometer, the telemetry collection service. To deploy Gnocchi to an
existing OpenStack cloud (which already includes Ceilometer):

    juju deploy gnocchi
    juju deploy memcached
    juju add-relation gnocchi:shared-db percona-cluster:shared-db
    juju add-relation gnocchi:coordinator-memcached memcached:cache
    juju add-relation gnocchi:identity-service keystone:identity-service
    juju add-relation gnocchi:storage-ceph ceph-mon:client
    juju add-relation gnocchi:metric-service ceilometer:metric-service

The Gnocchi API should now be used to service information queries. As such,
once re-configuration caused by the above relations has settled, the Ceilometer
API will be disabled.

Gnocchi then needs to be initialised with the current Ceilometer data:

    juju run-action --wait ceilometer/leader ceilometer-upgrade

## S3 storage backend support

The gnocchi charm by default uses Ceph as a storage backend (the default value
of option `storage-backend` is 'ceph') but it also has support for S3 storage.

> **Note**: S3 storage support is available starting with OpenStack Stein.

To configure Gnocchi to use S3 the following configuration options must be
set accordingly:

* `storage-backend`
* `s3-region-name`
* `s3-endpoint-url`
* `s3-access-key-id`
* `s3-secret-access-key`

See file `config.yaml` for more details on the above options.

## Policy overrides

Policy overrides is an advanced feature that allows an operator to override the
default policy of an OpenStack service. The policies that the service supports,
the defaults it implements in its code, and the defaults that a charm may
include should all be clearly understood before proceeding.

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

# Bugs

Please report bugs on [Launchpad][lp-bugs-charm-gnocchi].

For general charm questions refer to the [OpenStack Charm Guide][cg].

<!-- LINKS -->

[cg]: https://docs.openstack.org/charm-guide
[cdg]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide
[cdg-appendix-n]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/latest/app-policy-overrides.html
[juju-docs-config-apps]: https://juju.is/docs/configuring-applications
[lp-bugs-charm-gnocchi]: https://bugs.launchpad.net/charm-gnocchi/+filebug
[gnocchi-upstream]: https://wiki.openstack.org/wiki/Gnocchi
