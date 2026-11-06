module.exports = {
  apps: [{
    name: "teleops",
    script: "uvicorn",
    args: "app.main:app --host 0.0.0.0 --port 9100",
    interpreter: "none",
    cwd: __dirname,
    autorestart: true,
    max_restarts: 10,
  }]
}
