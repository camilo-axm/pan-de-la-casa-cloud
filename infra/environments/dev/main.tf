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

  features {
    key_vault {
      purge_soft_delete_on_destroy = true
    }
  }
}

variable "location" {
  type = string
}

variable "image" {
  type = string
}

variable "alert_email" {
  type    = string
  default = null
}

variable "owner_email" {
  description = "Correo de la cuenta inicial del dueño."
  type        = string
  default     = ""
}

variable "owner_password" {
  description = "Contraseña inicial del dueño, suministrada desde GitHub Actions."
  type        = string
  default     = ""
  sensitive   = true
}

variable "cosmos_free_tier" {
  type    = bool
  default = false
}

# El ambiente de Container Apps lo crea infra/environments/shared y lo usan dev y prod.
data "azurerm_container_app_environment" "shared" {
  name                = "cae-panaderia"
  resource_group_name = "rg-panaderia-shared"
}

module "stack" {
  source = "../../modules/stack"

  environment                  = "dev"
  location                     = var.location
  container_app_environment_id = data.azurerm_container_app_environment.shared.id
  image                        = var.image
  min_replicas                 = 0
  max_replicas                 = 1
  cosmos_free_tier             = var.cosmos_free_tier
  alert_email                  = var.alert_email
  monthly_budget_usd           = 5
  owner_email                  = var.owner_email
  owner_password               = var.owner_password
}

output "app_url" {
  value = module.stack.app_url
}

output "resource_group_name" {
  value = module.stack.resource_group_name
}

output "cosmos_account_name" {
  value = module.stack.cosmos_account_name
}
