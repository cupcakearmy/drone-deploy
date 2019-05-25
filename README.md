# Drone Deployment Plugin

## Quickstart 🚀

```yaml
kind: pipeline
name: default

steps:
  
  - name: build
    image: node:11-alpine
    pull: always
    commands:
      - npm i
      - npm run build:prod

  - name: deploy
    image: cupcakearmy/drone-deploy
    pull: always
    settings:
      host: example.org
      user: root
      key:
        from_secret: ssh_key
      port: 69
      target: /my/web/root/project
      sources:
        - ./public
        - ./docker-compose.yml
        - ./docker-compose.prod.yml
      commands:
        - docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
        - docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
    when:
      event: push
      branch: master
```

### Details 📒

The plugins creates a tarball compressing all the files included inside of `sources`.
Then the compressed tarball gets uploaded, extracted and deleted, leaving only the files specified by `sources` inside of the `target` folder.
Afterwards all the commands inside of `commands` will get executed at the `target` directory.

### Mapping remote environment variables 🗺

Sometimes it's usefull to have a remote env with a secret. Here is how.

```yaml
kind: pipeline
name: default

steps:

  # build...

  - name: deploy
    image: cupcakearmy/drone-deploy
    pull: always
    settings:
      # host, user, port, key, when, target ...

      myenv: 'Something'
      somesecret:
        from_secret: mysecret
      envs:
        - myvar
        - somesecret
      commands:
        - echo $MYENV # Outputs: Something
        - echo $SOMESECRET # Outputs: Whatever is saved in drone as `mysecret`
```