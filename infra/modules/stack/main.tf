terraform {
  required_version = ">= 1.11"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.12"
    }
  }
}

locals {
  name = "panaderia-${var.environment}"
  tags = {
    project     = "pan-de-la-casa"
    environment = var.environment
    managed_by  = "terraform"
  }
  is_prod = var.environment == "prod"
  # Las alertas necesitan a quien avisar: sin correo no se crean.
  alerts_enabled = try(length(var.alert_email) > 0, false)
}

# Los nombres de Key Vault y Cosmos DB son globales en todo Azure.
resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "random_password" "admin_key" {
  length  = 40
  special = false
}

locals {
  app_secrets = merge({
    "mongodb-uri"   = module.database.connection_string
    "admin-api-key" = random_password.admin_key.result
  }, var.owner_email != "" ? { "owner-password" = var.owner_password } : {})
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name}"
  location = var.location
  tags     = local.tags
}

module "database" {
  source = "../database"

  account_name        = "cosmos-${local.name}-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  free_tier           = var.cosmos_free_tier
  tags                = local.tags
}

module "key_vault" {
  source = "../key_vault"

  name                     = "kv-pan-${var.environment}-${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.this.name
  location                 = azurerm_resource_group.this.location
  purge_protection_enabled = local.is_prod
  rbac_propagation_wait    = var.rbac_propagation_wait
  tags                     = local.tags

  secrets = local.app_secrets
}

module "app" {
  source = "../container_app"

  name                   = local.name
  resource_group_name    = azurerm_resource_group.this.name
  location               = azurerm_resource_group.this.location
  environment_id         = var.container_app_environment_id
  image                  = var.image
  key_vault_id           = module.key_vault.id
  secret_ids             = module.key_vault.secret_ids
  secret_values          = var.container_apps_express ? local.app_secrets : {}
  container_apps_express = var.container_apps_express
  min_replicas           = var.min_replicas
  max_replicas           = var.max_replicas
  rbac_propagation_wait  = var.rbac_propagation_wait
  tags                   = local.tags

  environment_variables = merge({
    APP_ENV    = var.environment
    MONGODB_DB = module.database.database_name
  }, var.owner_email != "" ? { OWNER_EMAIL = var.owner_email } : {})
}

resource "azurerm_monitor_action_group" "ops" {
  count = local.alerts_enabled ? 1 : 0

  name                = "ag-${local.name}"
  resource_group_name = azurerm_resource_group.this.name
  short_name          = "panaderia"
  tags                = local.tags

  email_receiver {
    name                    = "operacion"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }
}

# Alerta de observabilidad: errores 5xx de la app durante 5 minutos.
resource "azurerm_monitor_metric_alert" "errores_5xx" {
  count = local.alerts_enabled ? 1 : 0

  name                = "alerta-5xx-${local.name}"
  resource_group_name = azurerm_resource_group.this.name
  scopes              = [module.app.id]
  description         = "La aplicacion respondio con errores 5xx."
  severity            = 1
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.tags

  criteria {
    metric_namespace = "Microsoft.App/containerApps"
    metric_name      = "Requests"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = var.alert_5xx_threshold

    dimension {
      name     = "statusCodeCategory"
      operator = "Include"
      values   = ["5xx"]
    }
  }

  action {
    action_group_id = azurerm_monitor_action_group.ops[0].id
  }
}

# Alerta de presupuesto del ambiente: avisa al 80 % del gasto real y al 100 % del proyectado.
resource "azurerm_consumption_budget_resource_group" "this" {
  count = local.alerts_enabled ? 1 : 0

  name              = "presupuesto-${local.name}"
  resource_group_id = azurerm_resource_group.this.id
  amount            = var.monthly_budget_usd
  time_grain        = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  notification {
    operator       = "GreaterThanOrEqualTo"
    threshold      = 80
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }

  notification {
    operator       = "GreaterThanOrEqualTo"
    threshold      = 100
    threshold_type = "Forecasted"
    contact_emails = [var.alert_email]
  }
}
