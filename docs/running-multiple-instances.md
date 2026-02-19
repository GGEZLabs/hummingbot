# Running Multiple Hummingbot Instances

Each Hummingbot instance (container) must use its own configuration folder and logs folder. This can be achieved by defining separate services in your docker-compose.yml file.

**Before starting,** please make sure the Hummingbot container starts at least once and the **password** is already configured. Additionally, it is **recommended** to configure the necessary connectors and create the strategy configuration before creating multiple instances.

1. ## Create a conf and logs folders for each instance

   1. ### Run the create new instance folders command

      Replace \<instance\_name\> with the actual instance name, it should be the same as \<instance\_name\> in the docker\_compose.yml

   sh create\_new\_instance\_folder.sh \<instance\_name\>

      this command  should create a conf/\<instance\_name\> folder with all required folders, and create logs/\<instance\_name\> folder

2. ## Define the first Hummingbot instance (build image)

The first instance should build the Docker image. Example of full service:

**\<HBot\_instance\_name\_1\>**:

  container\_name: **\<HBot\_instance\_name\_1\>**

  **build:**

    **context: .**

    **dockerfile: Dockerfile**

  image: hummingbot

  volumes:

    \- ./conf**/\<HBot\_instance\_name\_1\>**:/home/hummingbot/conf

    \- ./conf/connectors:/home/hummingbot/conf/connectors

    \- ./conf/strategies:/home/hummingbot/conf/strategies

    \- ./conf/controllers:/home/hummingbot/conf/controllers

    \- ./conf/scripts:/home/hummingbot/conf/scripts

    \- ./logs/**\<HBot\_instance\_name\_1\>**:/home/hummingbot/logs

    \- ./data:/home/hummingbot/data

    \- ./certs:/home/hummingbot/certs

    \- ./scripts:/home/hummingbot/scripts

    \- ./controllers:/home/hummingbot/controllers

  logging:

    driver: "json-file"

    options:

      max-size: "10m"

      max-file: "5"

  tty: true

  stdin\_open: true

  network\_mode: host

3. ## Define additional Hummingbot instances

   Subsequent instances only need the image: reference, since the image is already built. Example of full service:

   **\<HBot\_instance\_name\_2\>**:

     container\_name: **\<HBot\_instance\_name\_2\>**

     image: hummingbot

     volumes:

       \- ./conf/**\<HBot\_instance\_name\_2\>**:/home/hummingbot/conf

       \- ./conf/connectors:/home/hummingbot/conf/connectors

       \- ./conf/strategies:/home/hummingbot/conf/strategies

       \- ./conf/controllers:/home/hummingbot/conf/controllers

       \- ./conf/scripts:/home/hummingbot/conf/scripts

       \- ./logs/**\<HBot\_instance\_name\_2\>**:/home/hummingbot/logs

       \- ./data:/home/hummingbot/data

       \- ./certs:/home/hummingbot/certs

       \- ./scripts:/home/hummingbot/scripts

       \- ./controllers:/home/hummingbot/controllers

     logging:

       driver: "json-file"

       options:

         max-size: "10m"

         max-file: "5"

     tty: true

     stdin\_open: true

     network\_mode: host

   **Now these instances have the same**  connectors,  strategies, controllers, scripts and password, but **different**  conf\_client.yml, conf\_fee\_overrides.yml, hummingbot\_logs.yml and logs folder

4. ## Auto start containers with a preconfigured strategy

   To auto-run a preconfigured strategy for each instance,  in docker-compose.yml file, edit or add  the section that defines the environment variables:

     environment:

       \- CONFIG\_PASSWORD=**\<password\>**

       \- CONFIG\_FILE\_NAME=**\<strategy\_file\>**

       \- SCRIPT\_CONFIG=**\<strategy\_config\_file\>**

   Check the hummingbot documentation for more details

   [https://hummingbot.org/global-configs/strategy-autostart/\#how-to-autostart](https://hummingbot.org/global-configs/strategy-autostart/#how-to-autostart)

Now that two Hummingbot instances are running, you can attach to them, configure the connector and create the strategy config.
