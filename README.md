# Care Celery Flower

[Flower](https://flower.readthedocs.io/) monitoring for [Care](https://github.com/egovhealthcare/care), installed as a standard Care plug.

## Install

```python
Plug(
    name="care_celery_flower",
    package_name="git+https://github.com/egovhealthcare/care_celery_flower.git",
    version="@main",
    configs={
      # "FLOWER_PORT": 5555,
      # "FLOWER_BASIC_AUTH": "",  # format: user:password
      # "FLOWER_URL_PREFIX": "",
    },
)
```

```bash
export ADDITIONAL_PLUGS='[{"name":"care_celery_flower","package_name":"git+https://github.com/egovhealthcare/care_celery_flower.git","version":"@main"}]'
```

Native / editable:

```bash
pip install "git+https://github.com/egovhealthcare/care_celery_flower.git"
# or: pip install -e ../care_celery_flower

export DJANGO_SETTINGS_MODULE=config.settings.local  # or deployment
start-flower
```

| Config | Default | Description |
| --- | --- | --- |
| `FLOWER_PORT` | `5555` | Listen port |
| `FLOWER_BASIC_AUTH` | _(empty)_ | `user:password` |
| `FLOWER_URL_PREFIX` | _(empty)_ | Reverse-proxy prefix |
| `APP_HOME` / `CARE_HOME` | auto-detected | Care project root |

## Run


```yaml
celery-flower:
  image: "ghcr.io/egovhealthcare/care:latest"
  env_file:
    - ./docker/.prebuilt.env
  environment:
    FLOWER_PORT: "5555"
  entrypoint: ["start-flower"]
  ports:
    - "5555:5555"
  healthcheck:
    test: ["CMD", "curl", "-fsS", "http://localhost:5555/"]
    interval: 10s
    timeout: 5s
    retries: 12
    start_period: 20s
  restart: unless-stopped
  depends_on:
    redis:
      condition: service_started
    celery-worker:
      condition: service_started
```
