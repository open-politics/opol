mkdir -p ./opol/stack/.store/data/placeholder
chmod 777 ./opol/stack/.store/data/placeholder

cd opol/stack
mv .env.example .env
mv .env.local.example .env.local

sysctl -w vm.overcommit_memory=1

docker compose -f compose.local.yml up --build -d

sleep 10

sudo docker exec -it opol-ollama-1 ollama pull llama3.1