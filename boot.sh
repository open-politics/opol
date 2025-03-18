cd opol/

mkdir -p ./opol/stack/.store/data/placeholder
sudo chmod 777 ./opol/stack/.store/data/placeholder

cd opol/stack
cp .env.local .env
sudo docker network create opol-app-stack
sudo docker compose -f compose.local.yml up --build -d

bash boot-local.sh