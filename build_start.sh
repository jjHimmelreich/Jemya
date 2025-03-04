# Stop and remove all containers based on the image
docker ps -a | grep 'jemya' | awk '{print $1}' | xargs -r docker stop
docker ps -a | grep 'jemya' | awk '{print $1}' | xargs -r docker rm

# Remove the image
docker rmi jemya:latest

# Build new image
docker build -f "Dockerfile" -t jemya:latest "." 

# Start container from new image
docker run -d --name jemya -p 5555:5555 jemya:latest