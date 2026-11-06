module.exports = {
  apps: [{
    name: "teleops",
    script: "uvicorn",
    args: "app.main:app --port 9100",
    interpreter: "none",
    cwd: __dirname,
    autorestart: true,
    max_restarts: 10,
  }]
}
