# Pruebas sin nube: mock_provider no necesita credenciales.

mock_provider "azurerm" {
  mock_resource "azurerm_cosmosdb_account" {
    defaults = {
      id                                = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.DocumentDB/databaseAccounts/cosmos"
      primary_mongodb_connection_string = "mongodb://cosmos:clave@cosmos.mongo.cosmos.azure.com:10255/?ssl=true"
    }
  }
}

variables {
  account_name        = "cosmos-prueba"
  resource_group_name = "rg"
  location            = "centralus"
}

run "sin_capa_gratuita_es_serverless" {
  command = apply

  assert {
    condition     = contains([for c in azurerm_cosmosdb_account.this.capabilities : c.name], "EnableServerless")
    error_message = "Sin capa gratuita la cuenta debe ser serverless para no cobrar en reposo."
  }
  assert {
    condition     = length(azurerm_cosmosdb_mongo_database.this.autoscale_settings) == 0
    error_message = "Una cuenta serverless no admite throughput aprovisionado."
  }
  assert {
    condition     = output.serverless
    error_message = "La salida debe informar el modo serverless."
  }
}

run "con_capa_gratuita_autoescala_hasta_1000" {
  command = apply

  variables {
    free_tier = true
  }

  assert {
    condition     = azurerm_cosmosdb_account.this.free_tier_enabled
    error_message = "La capa gratuita debe quedar activa."
  }
  assert {
    condition     = !contains([for c in azurerm_cosmosdb_account.this.capabilities : c.name], "EnableServerless")
    error_message = "La capa gratuita y serverless no se pueden combinar."
  }
  assert {
    condition     = azurerm_cosmosdb_mongo_database.this.autoscale_settings[0].max_throughput == 1000
    error_message = "El tope debe quedar dentro de los 1000 RU/s gratuitos."
  }
}

run "siempre_mongodb_tls_y_respaldo_continuo" {
  command = apply

  assert {
    condition     = azurerm_cosmosdb_account.this.kind == "MongoDB"
    error_message = "La cuenta debe exponer la API de MongoDB."
  }
  assert {
    condition     = azurerm_cosmosdb_account.this.minimal_tls_version == "Tls12"
    error_message = "TLS 1.2 como minimo."
  }
  assert {
    condition     = azurerm_cosmosdb_account.this.backup[0].type == "Continuous"
    error_message = "El respaldo continuo sostiene el RPO de 24 horas."
  }
}

run "nombre_invalido_se_rechaza" {
  command = plan

  variables {
    account_name = "Cosmos_Prueba"
  }

  expect_failures = [var.account_name]
}
