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

From this directory, initialize the backend and inspect the shared state:

```sh
terraform init
terraform state list
```

The existing services and integration have already been imported into the shared
state. Imports are a one-time bootstrap operation, not a step for each user or
CI run. If bootstrapping a new, empty state, import all three resources:

```sh
terraform import aiven_pg.postgres junction2026/pg-1ad8c70c
terraform import aiven_grafana.grafana junction2026/grafana-2b2ab510
terraform import aiven_service_integration.grafana_postgres junction2026/3971957f-9e5e-4ff8-bc23-451256ac2063
```

Then review the plan:

```sh
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

## GitHub Actions

The Aiven Terraform workflow validates pull requests without credentials.
Changes under `infra/aiven/` merged to `main` automatically plan and apply;
the workflow can also be started manually on `main`. Deployments are serialized
and fail if any of the three existing resources is missing from shared state.
Automatic apply also refuses plans containing deletions or replacements.
There is no approval step, so protect `main` and review infrastructure changes
before merging. Terraform plans and applies can change live services.

Add these repository secrets under **Settings > Secrets and variables > Actions**:

- `AIVEN_TOKEN`: an Aiven API token with permission to manage the project.
- `TERRAFORM_STATE_PASSWORD`: the password for the `terraform_state` database user.
- `AIVEN_CA_CERT`: the complete Aiven project CA certificate in PEM format,
  including the BEGIN and END lines.

The workflow connects to the existing state database using TLS verification.
It does not upload the saved plan or use the local `.env` file. Do not expose
these secrets to pull requests from untrusted branches or print them in logs.
