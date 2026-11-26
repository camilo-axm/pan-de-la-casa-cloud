# Dev y prod comparten el entorno de Container Apps y Log Analytics.
# Cada ambiente mantiene su base de datos, Key Vault, identidad y grupo de recursos.

terraform {
  required_version = ">= 1.11"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
    }
  }

  # La cuenta de almacenamiento y la clave del archivo de estado se pasan con -backend-config.
  backend "azurerm" {
    use_azuread_auth = true
  }
}

# En GitHub Actions la identidad llega por OIDC (ARM_USE_OIDC y ARM_CLIENT_ID).
provider "azurerm" {
  storage_use_azuread             = true
  resource_provider_registrations = "none"
  features {}
}

variable "location" {
  type = string
}

locals {
  tags = {
    project     = "pan-de-la-casa"
    environment = "shared"
    managed_by  = "terraform"
  }
}

resource "azurerm_resource_group" "this" {
  name     = "rg-panaderia-shared"
  location = var.location
  tags     = local.tags
}

# Logs centralizados de los dos ambientes.
resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-panaderia"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.5 # Tope duro: los primeros 5 GB del mes son gratis y aqui no se supera.
  tags                = local.tags
}

resource "azurerm_container_app_environment" "this" {
  #checkov:skip=CKV_AZURE_227:La redundancia de zona exige una VNet propia, prevista para produccion
  name                       = "cae-panaderia"
  resource_group_name        = azurerm_resource_group.this.name
  location                   = azurerm_resource_group.this.location
  logs_destination           = "log-analytics"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  tags                       = local.tags

  # Azure lo agrega siempre; declararlo evita un cambio perpetuo en cada plan. No tiene cargo fijo.
  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}

output "container_app_environment_id" {
  value = azurerm_container_app_environment.this.id
}

output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.this.id
}
