# Pruebas sin nube: mock_provider no necesita credenciales ni emulador.

mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      tenant_id = "00000000-0000-0000-0000-000000000001"
      object_id = "00000000-0000-0000-0000-000000000002"
    }
  }
  mock_resource "azurerm_resource_group" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg"
    }
  }
  mock_resource "azurerm_key_vault" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv"
    }
  }
  mock_resource "azurerm_key_vault_secret" {
    defaults = {
      versionless_id = "https://kv.vault.azure.net/secrets/secreto"
    }
  }
  mock_resource "azurerm_cosmosdb_account" {
    defaults = {
      id                                = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.DocumentDB/databaseAccounts/cosmos"
      primary_mongodb_connection_string = "mongodb://cosmos:clave@cosmos.mongo.cosmos.azure.com:10255/?ssl=true"
    }
  }
  mock_resource "azurerm_user_assigned_identity" {
    defaults = {
      id           = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id"
      principal_id = "00000000-0000-0000-0000-000000000003"
    }
  }
  mock_resource "azurerm_container_app" {
    defaults = {
      id      = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.App/containerApps/ca"
      ingress = { fqdn = "panaderia.azurecontainerapps.io" }
    }
  }
  mock_resource "azurerm_monitor_action_group" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Insights/actionGroups/ag"
    }
  }
}

mock_provider "random" {}
mock_provider "time" {}

variables {
  location                     = "centralus"
  image                        = "ghcr.io/eci/pan-de-la-casa@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  container_app_environment_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-panaderia-shared/providers/Microsoft.App/managedEnvironments/cae-panaderia"
  rbac_propagation_wait        = "1s"
}

run "dev_es_barato_y_desechable" {
  command = apply

  variables {
    environment = "dev"
  }

  assert {
    condition     = azurerm_resource_group.this.name == "rg-panaderia-dev"
    error_message = "El grupo de recursos debe incluir el ambiente."
  }
  assert {
    condition     = azurerm_resource_group.this.tags["environment"] == "dev"
    error_message = "Las etiquetas deben identificar el ambiente."
  }
  assert {
    condition     = startswith(output.app_url, "https://")
    error_message = "La URL publica debe ser HTTPS."
  }
  assert {
    condition     = local.is_prod == false
    error_message = "dev no debe activar la proteccion de prod."
  }
  assert {
    condition     = length(azurerm_monitor_metric_alert.errores_5xx) == 0
    error_message = "Sin correo no se deben crear alertas."
  }
}

run "dev_guarda_la_clave_del_dueno_en_key_vault" {
  command = apply

  variables {
    environment            = "dev"
    owner_email            = "dueno@example.com"
    owner_password         = "clave-solo-para-pruebas"
    container_apps_express = true
  }

  assert {
    condition     = contains(keys(module.key_vault.secret_ids), "owner-password")
    error_message = "La contraseña inicial debe tener una referencia en Key Vault."
  }
}

run "prod_escala_y_avisa" {
  command = apply

  variables {
    environment      = "prod"
    min_replicas     = 1
    max_replicas     = 3
    cosmos_free_tier = true
    alert_email      = "operacion@example.com"
  }

  assert {
    condition     = local.is_prod
    error_message = "prod debe proteger su Key Vault contra purgas."
  }
  assert {
    condition     = length(azurerm_monitor_metric_alert.errores_5xx) == 1
    error_message = "prod debe tener la alerta de errores 5xx."
  }
  assert {
    condition     = azurerm_consumption_budget_resource_group.this[0].amount == 20
    error_message = "prod debe tener alerta de presupuesto."
  }
  assert {
    condition     = module.database.serverless == false
    error_message = "prod usa la capa gratuita con autoescala."
  }
}

run "la_imagen_debe_ir_por_digest" {
  command = plan

  variables {
    environment = "dev"
    image       = "ghcr.io/eci/pan-de-la-casa:latest"
  }

  expect_failures = [var.image]
}

run "ambiente_desconocido_se_rechaza" {
  command = plan

  variables {
    environment = "staging"
  }

  expect_failures = [var.environment]
}

run "el_tope_de_replicas_protege_el_presupuesto" {
  command = plan

  variables {
    environment  = "prod"
    max_replicas = 10
  }

  expect_failures = [var.max_replicas]
}
