#!/bin/bash
set -e

USER=$1
NAMESPACE=$2

if [ -z "$USER" ] || [ -z "$NAMESPACE" ]; then
    echo "Usage: $0 <username> <namespace>"
    exit 1
fi

PVC_NAME="claim-${USER}"
BACKUP_PVC_NAME="${PVC_NAME}-backup"

echo "Migrating PVC $PVC_NAME in namespace $NAMESPACE..."

# Delete user pod to release PVC
POD_NAME="jupyter-${USER}"
echo "Stopping user pod $POD_NAME to release PVC..."
kubectl delete pod $POD_NAME -n $NAMESPACE --ignore-not-found=true --wait=true

# Check if PVC exists
kubectl get pvc $PVC_NAME -n $NAMESPACE > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "PVC $PVC_NAME does not exist in namespace $NAMESPACE"
    exit 1
fi

# Check if already RWX
ACCESS_MODE=$(kubectl get pvc $PVC_NAME -n $NAMESPACE -o jsonpath='{.spec.accessModes[0]}')
if [ "$ACCESS_MODE" == "ReadWriteMany" ]; then
    echo "PVC $PVC_NAME is already ReadWriteMany"
    exit 0
fi

# Get PVC size
PVC_SIZE=$(kubectl get pvc $PVC_NAME -n $NAMESPACE -o jsonpath='{.spec.resources.requests.storage}')
echo "Detected PVC size: $PVC_SIZE"

echo "Creating backup PVC..."
cat <<EOF | kubectl apply -n $NAMESPACE -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: $BACKUP_PVC_NAME
spec:
  storageClassName: longhorn-fast
  dataSource:
    name: $PVC_NAME
    kind: PersistentVolumeClaim
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: $PVC_SIZE
EOF

echo "Waiting for backup PVC to be bound..."
for i in {1..60}; do
  PHASE=$(kubectl get pvc $BACKUP_PVC_NAME -n $NAMESPACE -o jsonpath='{.status.phase}')
  if [ "$PHASE" == "Bound" ]; then
    echo "Backup PVC is Bound."
    break
  fi
  if [ $i -eq 60 ]; then
    echo "Timeout waiting for backup PVC to bind."
    exit 1
  fi
  sleep 5
done

echo "Deleting original PVC..."
kubectl delete pvc $PVC_NAME -n $NAMESPACE --wait=true

echo "Creating new RWX PVC..."
cat <<EOF | kubectl apply -n $NAMESPACE -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: $PVC_NAME
spec:
  storageClassName: longhorn-fast
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: $PVC_SIZE
EOF

echo "Waiting for new PVC to be bound..."
for i in {1..60}; do
  PHASE=$(kubectl get pvc $PVC_NAME -n $NAMESPACE -o jsonpath='{.status.phase}')
  if [ "$PHASE" == "Bound" ]; then
    echo "New PVC is Bound."
    break
  fi
  if [ $i -eq 60 ]; then
    echo "Timeout waiting for new PVC to bind."
    exit 1
  fi
  sleep 5
done

echo "Starting migration pod..."
cat <<EOF | kubectl apply -n $NAMESPACE -f -
apiVersion: v1
kind: Pod
metadata:
  name: migration-$USER
spec:
  restartPolicy: Never
  containers:
  - name: rsync
    image: alpine:latest
    command: ["/bin/sh", "-c", "apk add --no-cache rsync && rsync -av --delete /mnt/backup/ /mnt/new/ && echo 'Migration Complete'"]
    volumeMounts:
    - name: backup
      mountPath: /mnt/backup
      readOnly: true
    - name: new
      mountPath: /mnt/new
  volumes:
  - name: backup
    persistentVolumeClaim:
      claimName: $BACKUP_PVC_NAME
  - name: new
    persistentVolumeClaim:
      claimName: $PVC_NAME
EOF

echo "Waiting for migration to complete..."
kubectl wait --for=condition=Ready pod/migration-$USER -n $NAMESPACE --timeout=300s
kubectl logs -f migration-$USER -n $NAMESPACE

echo "Cleaning up..."
kubectl delete pod migration-$USER -n $NAMESPACE
kubectl delete pvc $BACKUP_PVC_NAME -n $NAMESPACE

echo "Migration of $PVC_NAME to RWX completed successfully."
