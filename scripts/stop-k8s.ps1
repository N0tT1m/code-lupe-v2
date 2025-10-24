# Stop Kubernetes deployment
Write-Host "Stopping CodeLupe Kubernetes Pipeline..." -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Red

Write-Host "Deleting deployments..." -ForegroundColor Yellow
kubectl delete -f kubernetes/trainer.yaml
kubectl delete -f kubernetes/processor.yaml  
kubectl delete -f kubernetes/monitoring.yaml
kubectl delete -f kubernetes/postgres.yaml

Write-Host "Deleting namespace..." -ForegroundColor Yellow
kubectl delete -f kubernetes/namespace.yaml

Write-Host ""
Write-Host "Pipeline stopped successfully!" -ForegroundColor Green
Write-Host "To restart: .\start-k8s.ps1"