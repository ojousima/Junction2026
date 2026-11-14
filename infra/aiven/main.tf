terraform {
  required_version = ">= 1.5.0, < 2.0.0"

  required_providers {
    aiven = {
      source  = "aiven/aiven"
      version = "~> 4.66.0"
    }
  }

  backend "pg" {}
}

provider "aiven" {}

resource "aiven_pg" "postgres" {
  project                 = "junction2026"
  service_name            = "pg-1ad8c70c"
  cloud_name              = "google-europe-north1"
  plan                    = "business-4"
  maintenance_window_dow  = "thursday"
  maintenance_window_time = "09:52:58"
  termination_protection  = false

  pg_user_config {
    pg_version             = "18"
    backup_hour            = 19
    backup_minute          = 7
    enable_ha_replica_dns  = false
    ip_filter_string       = ["0.0.0.0/0", "::/0"]
    pg_stat_monitor_enable = false
    pg_stat_plans_enable   = false

    pg {
      io_combine_limit     = 16
      io_max_combine_limit = 16
      io_max_concurrency   = -1
      io_method            = "worker"
      password_encryption  = "scram-sha-256"
    }

    pglookout {
      max_failover_replication_time_lag = 60
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aiven_grafana" "grafana" {
  project                 = "junction2026"
  service_name            = "grafana-2b2ab510"
  cloud_name              = "google-europe-north1"
  plan                    = "startup-4"
  maintenance_window_dow  = "thursday"
  maintenance_window_time = "03:23:44"
  termination_protection  = false

  grafana_user_config {
    grafana_version  = "11"
    ip_filter_string = ["0.0.0.0/0", "::/0"]
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aiven_service_integration" "grafana_postgres" {
  project                  = "junction2026"
  integration_type         = "datasource"
  source_service_name      = aiven_grafana.grafana.service_name
  destination_service_name = aiven_pg.postgres.service_name

  lifecycle {
    prevent_destroy = true
  }
}
