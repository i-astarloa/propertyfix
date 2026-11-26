# Prompts 02 — Del MVP a los entregables (25–26/11/2026)

Peticiones relevantes del equipo a Claude Code, en orden:

1. «Usa una API abierta/gratuita como Ollama para no pagar nada.» → modelo local Qwen 2.5 3B.
2. «Una web en la que la persona inicie sesión con su email, explique el problema de su vivienda, y la web busque el mejor proveedor por precio, ubicación y especialidad; que agende la cita en su Google Calendar, le mande un email de confirmación y un documento con el mejor presupuesto. Inventa las bases de datos de proveedores.» → flujo completo con Gmail, Calendar, Drive y Sheets; 27 proveedores ficticios con semilla 42.
3. «Que al iniciar sesión en la web se inicie sesión en Google y funcione con la cuenta que entre; solo autorizamos la cuenta del proyecto.» → OAuth en modo prueba con un único usuario autorizado.
4. «No siempre clasifica bien: le dije que se rompió el lavavajillas y buscó una empresa de pintura. Igual tienes que entrenar mejor el modelo.» → evaluación con casos anotados, clasificador en dos pasos con verificador; 33 % → 83 % en un examen ciego.
5. «Vuelve a mirar las instrucciones y hazme memoria.pdf y slides.pdf.» → memoria y pitch generados desde los resultados medidos.
