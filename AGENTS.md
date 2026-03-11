Adicionalmente siempre se debe:
* Nunca cargar en el contexto los directorios y sus archivos
  - node_modules/
  - htmlcov/
  - .proyects/
  - .plans/
  - notebooks/
* Actualizar CLAUDE.md y toda la documentación si fuera necesario.
* Comprobar y arreglar los tests.
* Comprobar las reglas pre-commit y asgurarse de que pasen los controles.
* No utilizar "prints" para hacer logging. Utilizar en su lugar el modulo python de logging correspondiente.
* Utilizar siempre el comando colgrep para realizar búsquedas en el codigo.

Por favor, hazme todas las preguntas que consideres necesarias para hacer un refactor exitoso.