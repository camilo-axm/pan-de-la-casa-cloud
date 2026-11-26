output "id" {
  description = "ID de la Container App."
  value       = azurerm_container_app.this.id
}

output "url" {
  description = "URL publica HTTPS."
  value       = "https://${azurerm_container_app.this.ingress[0].fqdn}"
}

output "identity_principal_id" {
  description = "Identidad con la que la app lee sus secretos."
  value       = azurerm_user_assigned_identity.app.principal_id
}
