output "id" {
  description = "ID de la cuenta."
  value       = azurerm_cosmosdb_account.this.id
}

output "name" {
  description = "Nombre de la cuenta."
  value       = azurerm_cosmosdb_account.this.name
}

output "database_name" {
  description = "Base de datos de la aplicacion."
  value       = azurerm_cosmosdb_mongo_database.this.name
}

output "connection_string" {
  description = "Cadena de conexion de MongoDB. Solo debe viajar hacia Key Vault."
  value       = azurerm_cosmosdb_account.this.primary_mongodb_connection_string
  sensitive   = true
}

output "serverless" {
  description = "Indica si la cuenta quedo en modo serverless."
  value       = !var.free_tier
}
