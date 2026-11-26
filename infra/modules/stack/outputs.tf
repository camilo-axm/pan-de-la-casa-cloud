output "app_url" {
  description = "URL publica de la aplicacion."
  value       = module.app.url
}

output "resource_group_name" {
  description = "Grupo de recursos del ambiente."
  value       = azurerm_resource_group.this.name
}

output "cosmos_account_name" {
  description = "Cuenta de Cosmos DB, necesaria para restaurar un respaldo."
  value       = module.database.name
}
