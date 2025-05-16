# render.yaml
databases:
  - name: bootcamp_db
    databaseName: bootcamp_db
    user: bootcamp_user
    plan: free

services:
  - type: web
    name: bootcamp
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: bootcamp_db
          property: connectionString
      - key: FLASK_ENV
        value: production
      - key: SECRET_KEY
        generateValue: true
    healthCheckPath: /api/bootcamps