#!/bin/bash
# Smoke Test: Ingest 3 FAQs PDFs to LightRAG
# Tests: Serialization, API Key auth, Persistence

API_URL="https://lightrag-eudi-service-production.up.railway.app/ingest"
API_KEY="4091cd44992345dc5f8e705539fa7efae348b9f2e3a449d12b1f465d53c43923"
PDF_DIR="/Users/moisesmenendez/Documents/Prueba"

echo "🚀 LightRAG Smoke Test - Ingesting 3 FAQs"
echo "==========================================="

# Check if pdftotext is available
if ! command -v pdftotext &> /dev/null; then
    echo "⚠️  pdftotext not found. Installing via poppler..."
    brew install poppler
fi

count=0
for pdf in "$PDF_DIR"/*.pdf; do
    filename=$(basename "$pdf")
    echo ""
    echo "📄 Processing: $filename"
    
    # Extract text from PDF
    text=$(pdftotext "$pdf" - 2>/dev/null | head -c 50000)  # Limit to 50KB
    
    if [ -z "$text" ]; then
        echo "   ⚠️  Could not extract text, skipping"
        continue
    fi
    
    # Escape JSON special characters
    escaped_text=$(echo "$text" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')
    
    # Build doc_id for idempotency
    doc_id="${filename}_$(date +%Y%m%d)"
    
    # Ingest via API
    response=$(curl -s -X POST "$API_URL" \
        -H "Content-Type: application/json" \
        -H "x-api-key: $API_KEY" \
        -d "{
            \"text\": $escaped_text,
            \"metadata\": {
                \"source\": \"smoke_test\",
                \"filename\": \"$filename\",
                \"doc_id\": \"$doc_id\",
                \"category\": \"EUDI_FAQ\"
            }
        }")
    
    echo "   Response: $response"
    ((count++))
    
    # Wait 2 seconds between ingests to allow processing
    echo "   ⏳ Waiting 2s for graph processing..."
    sleep 2
done

echo ""
echo "==========================================="
echo "✅ Ingested $count documents"
echo ""
echo "Next steps:"
echo "1. Check Railway logs for [INGEST COMPLETE] x3"
echo "2. Run query test:"
echo '   curl -X POST "https://lightrag-eudi-service-production.up.railway.app/query" \'
echo '     -H "Content-Type: application/json" \'
echo '     -H "x-api-key: '$API_KEY'" \'
echo '     -d '\''{"query": "What is EUDI Wallet?", "mode": "hybrid"}'\'''
