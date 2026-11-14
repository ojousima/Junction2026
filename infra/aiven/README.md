# Aiven infrastructure

Terraform configuration for the existing PostgreSQL and Grafana services and
their datasource integration in the `junction2026` project. This is an adoption
configuration: import the existing resources before considering an apply.
It does not manage database users, schemas, Grafana dashboards, or other data.

## Remote state bootstrap

Terraform uses its PostgreSQL backend on the existing Aiven PostgreSQL service.
This is a bootstrap dependency: if that service is unavailable, Terraform
cannot access its own state or locks. Back up the database and establish an
independent recovery process before relying on it. Do not delete or replace
the service while using it as a backend.

State may contain service credentials, even when marked sensitive. Restrict
access to the database, its backups, and the Terraform state schema to trusted
operators. The state backend uses PostgreSQL advisory locks and requires a
direct connection to the primary PostgreSQL port, not PgBouncer.

1. Install Terraform 1.5 or later and create an Aiven API token with the
   necessary project permissions. Do not commit the token.
2. The `terraform_state` database and user have been created on the existing
   PostgreSQL service. The database user has `CONNECT` and `CREATE` privileges,
   while `grafana` and `sensor_writer` cannot connect. For a new setup, an
   authorized database administrator can configure these privileges with the
   following SQL (the MCP SQL tool cannot run these commands):

   ```sql
   REVOKE CONNECT ON DATABASE terraform_state FROM PUBLIC;
   GRANT CONNECT, CREATE ON DATABASE terraform_state TO terraform_state;
   ```

   Check for any other explicit grants or privileged roles and restrict them as
   appropriate. Do not initialize the backend until access is restricted; state
   can contain credentials. The backend user creates and owns its state schema.
   Ensure the database is included in backups.

   Terraform 1.17 also creates a sequence in the `public` schema. Connect as
   an administrator to the `terraform_state` database and run:

   ```sql
   GRANT CREATE ON SCHEMA public TO terraform_state;
   ```
3. Download the Aiven project CA certificate using the Aiven Console. From this
   directory, create a private local environment file:

   ```bash
   umask 077
   cp .env.example .env
   ```

   Place the CA certificate at `infra/aiven/aiven-ca.pem` and edit `.env` to
   set the Aiven token and database password. The certificate path is resolved
   from the Git repository root when `.env` is sourced from within the
   repository. The file is gitignored, but still contains secrets: restrict
   file access and never commit or share it. Values must be valid shell
   assignments; escape special characters appropriately. `verify-full` checks
   both the certificate and hostname.

   Load the file before running Terraform:

   ```bash
   set -a
   source .env
   set +a
   ```

   Only source a file you trust: sourcing executes shell code. These variables
   are needed for every Terraform command that accesses the backend. In CI,
   use CI secrets and a securely supplied CA certificate instead of `.env`.

## Import and verify

From this directory, initialize and import all three existing resources:

```sh
terraform init
terraform import aiven_pg.postgres junction2026/pg-1ad8c70c
terraform import aiven_grafana.grafana junction2026/grafana-2b2ab510
terraform import aiven_service_integration.grafana_postgres junction2026/3971957f-9e5e-4ff8-bc23-451256ac2063
terraform plan
```

Imports write remote state but do not modify the services. Review the plan
carefully and reconcile any differences with the live configuration before
applying: provider defaults or settings not captured here can produce changes.
Do not apply a plan that creates, replaces, deletes, or unexpectedly changes
the existing services or integration. The `prevent_destroy` guards protect
against accidental destruction while these resource blocks remain in the
configuration; they do not protect resources after their blocks are removed.

The current public IP filters and disabled Aiven termination protection mirror
the observed configuration; they are not recommended security settings. Changing
them requires a deliberate, separately reviewed plan. The datasource
integration was reported as "Setting up" when this configuration was written;
check its health separately in Aiven.

The lock file should be committed. Never commit state, credentials, saved plan
files, `.terraform/`, or backend configuration containing passwords.
