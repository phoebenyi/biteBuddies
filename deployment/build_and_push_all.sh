#!/bin/bash

USERNAME="phoebenyi"
DOCKERFILE_DIR="./backend"

SERVICES=(
  accept_request
  account
  availability
  chatbot
  composite_chatbot
  find_meeting
  find_partners
  forwarder
  meeting
  notif
  post_meeting
  restaurant
  search
  send_request
  transcribe
)

for SERVICE in "${SERVICES[@]}"; do
  IMAGE_NAME="$USERNAME/$SERVICE:latest"
  DOCKERFILE_PATH="$DOCKERFILE_DIR/Dockerfile.$SERVICE"
  
  echo "Building $SERVICE from $DOCKERFILE_PATH..."
  docker build -t "$IMAGE_NAME" -f "$DOCKERFILE_PATH" . || exit 1

  echo "Pushing $IMAGE_NAME..."
  docker push "$IMAGE_NAME" || exit 1

  echo "Done with $SERVICE"
  echo "------------------------"
done
