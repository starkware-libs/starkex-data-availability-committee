# Committee Service

**A service to validate the data availability for a Starkware application**

## Disclaimer
The source code provided in this repo is meant to serve as a <em>reference implementation</em> for
anyone who wishes to run a StarkEx data-availability committee node.
This implementation **should not be used to run a committee node in a production environment!**

## Description
The Starkware application holds a state of accounts that are updated according to an
ordered series of transactions. It processes transactions in batches of varying sizes, based on size
and time criteria. Following each batch, a Merkle tree is computed over all accounts resulting in
a Merkle root representing the state following the batch which is eventually to be committed
on-chain. Since only the root is committed on-chain, some mechanism is required to guarantee data-availability
in case the operator goes rogue (thus assuring end users of self-custody).

The Starkware application relies on a committee to guarantee data-availability of the off-chain data.
Each committee member is responsible for keeping track of the data associated with
each root and signing an availability claim to attest to the data-availability.

The Starkware application operator provides the committee members access to an Availability Gateway.
The Availability Gateway allows the committee members to obtain information about new batches
and to submit signed availability claims.

It is important to note that in order for batches to be accepted onchain they must be signed by a
minimum number of committee members (depending on the application configuration), including all
members who are defined as **mandatory signers**.

## What is a batch?

A batch is uniquely identifiable by its batch_id.
The information about a new batch includes a reference batch_id and a list of (index, value) pairs
with the new values of the accounts that changed relative to the reference batch.
The service combines this information with the data from the reference batch, to compute the new
state and root.
Typically the reference batch is the immediate predecessor of the new batch. However, due to the
nature of the blockchain, it is possible that a batch created by the Starkware application is later
reverted and replaced by a different batch.

## Running the Committee Service

### Configuration

The docker image expects to find a `config.yaml` file in its root directory. This file should be
mounted to the docker at run time.

Service operators are expected to do the following:
For StarkEx Perpetual committee, start by replacing the content of `config.yml` file with the content of `perpetual_config.yml`.
The `config.yml` file should be edited to reflect the specific configuration of the Committee Service operator.
In particular, this should include the following information:
- `private_key_path` - where the private key for signing availability claims is mounted.
- `certificates_path` - where the TLS certificates (`user.crt`, `user.key` and `server.crt`) for
  the Availability Gateway are mounted.
- `availability_gateway_endpoint` - The address of the Availability Gateway.
This information should be written in the docker-compose file as well, in the committee volumes section.

The default, for both the config and the docker-compose, is to have a file named config.yml at the root directory containing the config,
a file named private_key.txt in the root directory containing the private key
and a directory named certs in the root directory containing server.crt, user.crt and user.key.
Your files layout should resemble the following:
  > ROOT:
    | config.yml
    | private_key.txt
    | certs:
      | server.crt
      | user.crt
      | user.key

### Storage

A committee member service operator is expected to run a database
and update the STORAGE section of the `config.yml` with the information required to connect to said
database. The reference implementation uses an Aerospike database.

#### Setting-up Persistent Data Storage
In order to set up a storage directory for the committee Aerospike database:
- Create a directory. Disk-space requirement: 40 GB.
- Edit docker-compose.yml. In line 10, replace `<host volume>` with the directory path.
  For example.: `- ./committee-storage:/opt/aerospike/data/`

#### Mandatory Signers In Production
For committee members that are defined as mandatory signers we recommend the following settings for
the production environment:

- EC2 with strong consistency.
  - For Aerospike this will require the enterprise edition. For more details [click here](https://docs.aerospike.com/server/operations/configure/consistency).
- Recommend setting a `replication-factor` of `2` (the default is `1`).
  - This will require setting up 3 servers.
- Make sure the `default-ttl` setting is set to `0`.

#### Non-Mandatory Signers
For committee members that are defined as non-mandatory signers we recommend the following settings
for the production environment:

- EC2 is recommended.
  - Alternatively, multiple instances of docker-compose should be deployed to offer some resilience.
- Make sure the `default-ttl` setting is set to `0`.

## Deployment
In order to build the committee service, use the following line from the root directory:
```
docker-compose build
```

In order to run the committee service, use the following line from the root directory:
```
docker-compose up
```

## Publishing Committee Members Data
In the event that the Stark Exchange service malfunctions, becomes non-responsive or even malicious,
users eventually have the option to freeze it. Once frozen, a Committee member should publish the
accounts data for the latest root that appears on the on-chain contract.
Users can then use this data to exit the system even without the cooperation of Starkware.
To extract this data from the database, a `dump_trees.py` script is provided herein.

## Security and Privacy Considerations
The Committee Service operator is expected to apply best practices with respect to ensuring the
security of the service which is critical to the operation of the Starkware application as well as
best practices for protecting the data it receives contained in the batch updates.

## Copyright
Copyright 2022 StarkWare Industries Ltd.

Licensed under the Apache License, Version 2.0 (the "License").
You may not use this file except in compliance with the License.
You may obtain a copy of the License at

https://www.starkware.co/open-source-license/

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions
and limitations under the License.
