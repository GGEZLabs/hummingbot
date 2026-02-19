# HBot Instance

## Local server

* dghbot-1       ( 1 core, 16 GB ram , 4 GB swap )
  The local server hosts the source code for all Hummingbot components, including the CLI, dashboard, backend API, API client, and gateway, for setups 2.2 and 2.7. This server is also utilised for two main purposes: launching monitoring scripts and building Docker images before they are uploaded to ECR.

  * IP Address: `<LOCAL_SERVER_IP>`
    * docker container :
      * HBot CLI 2.7 ( volume monitor script )
      * HBot CLI 2.7 ( random transactions script)
      * HBot Dashboard  2.7 \=\> `http://<LOCAL_SERVER_IP>:8501/`
      * HBot Backend API   2.7
      * Hbot Gateway  2.7

	Both Hbot CLI and Hbot backend api connected to a self-hosted (using docker ) PostgreSQL server; also, Hbot Dashboard is connected to demo GGEZ1 Hasura GraphQL.


## Live instances ( Iweb )

*  **g-hbot-1**   ( 4 cores , 8 GB ram , 4 GB swap )

		backup ready to use container ( no architecture service, only volume orders )

* IP Address: `<IWEB_SERVER_IP>`
  * docker container :
    * HBot 2.2 (hummingbot-1) ( volume pumper on coinstore )
    * HBot 2.2 (hummingbot-2) ( random chain transactions )
    * HBot 2.2 (hummingbot-3) ( volume pumper on p2b )
    * HBot 2.2 (hummingbot-4) ( volume pumper on uzx )

    All HBot CLI containers are connected to the live GGEZ1 iweb PostgreSQL server server using private ip address ( `<IWEB_DB_PRIVATE_IP>`:5432 ) on the "market" schema.


## Live Instances ( AWS )

* **g-hbot-1-12-prod**    ( 4 cores , 8 GB ram , 4 GB swap )
  * IP Address: `<AWS_PROD_1_IP>`
  * Docker containers :
    * HBot CLI 2.7 ( Coinstore volume pumper controller )
    * HBot CLI 2.7 ( P2B volume pumper controller )
    * HBot CLI 2.7 ( UZX volume pumper controller )
    * HBot Dashboard  2.7 \=\> `https://<AWS_PROD_1_IP>/`
    * HBot Backend API   2.7

	All HBot CLI containers and HBot Backend API are connected to live GGEZ1 iweb PostgreSQL server using public ip address  ( `<IWEB_DB_PUBLIC_IP>`:5432 ) on "market" schema, also Hbot Dashboard is connected to live GGEZ1 Hasura GraphQL.

* **g-hbot-2-12-prod**    ( 2 cores , 4 GB ram , 0 GB swap ) down

  * IP Address: `<AWS_PROD_2_IP>`

  * Docker containers :
    * HBot Dashboard  2.7
    * HBot Backend API   2.7
