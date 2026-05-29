import os

def aggregate_files(original_filename, source_dir, output_filepath, num_chunks=4):
    """Aggregates chunk files back into a single file."""
    
    print(f"Aggregating {num_chunks} parts into '{output_filepath}'...")
    
    # Open the final output file in append/binary mode
    with open(output_filepath, 'wb') as outfile:
        for i in range(num_chunks):
            chunk_filename = f"{original_filename}.part{i+1}"
            chunk_filepath = os.path.join(source_dir, chunk_filename)
            
            # Verify the chunk exists before trying to read it
            if not os.path.exists(chunk_filepath):
                print(f"Error: Missing chunk {chunk_filepath}. Aggregation aborted.")
                return
                
            # Read the chunk and append it to the main file
            with open(chunk_filepath, 'rb') as infile:
                outfile.write(infile.read())
                
            print(f"Appended: {chunk_filepath}")
            
    print(f"Aggregation complete! Restored file saved as: {output_filepath}")

# --- Example Usage ---
if __name__ == "__main__":
    # The name of the original file (used to find the .part files)
    base_name = "bq_result.json"
    chunk_directory = "./bq_result_splitted"
    restored_file = "restored_bq_result.json"
    
    aggregate_files(base_name, chunk_directory, restored_file)