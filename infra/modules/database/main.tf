terraform {
  required_version = ">= 1.11"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
    }
  }
}

# Cosmos DB con la API de MongoDB: la aplicacion usa el driver pymongo sin cambios.
resource "azurerm_cosmosdb_account" "this" {
  #checkov:skip=CKV_AZURE_99:El MVP no tiene VNet; el acceso exige TLS 1.2 y la clave guardada en Key Vault
  #checkov:skip=CKV_AZURE_101:Container Apps en consumo no tiene IP de salida fija para un firewall
  #checkov:skip=CKV_AZURE_100:La llave administrada por Microsoft basta; CMK exige mas infraestructura
  #checkov:skip=CKV_AZURE_140:La API de MongoDB solo autentica con la clave de la cuenta
  #checkov:skip=CKV_AZURE_132:Terraform administra la cuenta con sus claves de gestion
  name                = var.account_name
  resource_group_name = var.resource_group_name
  location            = var.location
  offer_type          = "Standard"
  kind                = "MongoDB"
  tags                = var.tags

  mongo_server_version = "7.0"
  minimal_tls_version  = "Tls12"

  # La capa gratuita (1000 RU/s y 25 GB) solo existe una vez por suscripcion: la usa prod.
  free_tier_enabled = var.free_tier

  capabilities {
    name = "EnableMongo"
  }

  # La cuenta usa capacidad serverless cuando no se habilita la capa gratuita.
  dynamic "capabilities" {
    for_each = var.free_tier ? [] : ["EnableServerless"]
    content {
      name = capabilities.value
    }
  }

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = var.location
    failover_priority = 0
  }

  # Retención de siete días para restauración a un punto en el tiempo.
  backup {
    type = "Continuous"
    tier = "Continuous7Days"
  }
}

resource "azurerm_cosmosdb_mongo_database" "this" {
  name                = var.database_name
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.this.name

  # Autoescala de 100 a 1000 RU/s compartidos entre colecciones, dentro de la capa gratuita.
  dynamic "autoscale_settings" {
    for_each = var.free_tier ? [1] : []
    content {
      max_throughput = 1000
    }
  }
}
