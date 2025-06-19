# Generate RRI Map benchmark data
cd ..
echo "Generating RRI Map benchmark data..."
rustpython src/cli.py rri map --benchmark --method all
echo "Benchmark data generation complete."