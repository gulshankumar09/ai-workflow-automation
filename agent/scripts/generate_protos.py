#!/usr/bin/env python3
"""
Protocol Buffer Code Generation Script for ai-workflow-automation Core.

This script generates Python code from .proto files using the gRPC tools.
It handles all protocol buffer schemas and creates the necessary Python modules.
"""

import os
import sys
import subprocess
from pathlib import Path

def generate_protos():
    """Generate Python code from protocol buffer files."""
    
    # Get the project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    proto_dir = project_root / "app" / "interfaces" / "grpc" / "protos"
    
    # Ensure the proto directory exists
    if not proto_dir.exists():
        print(f"❌ Proto directory not found: {proto_dir}")
        return False
    
    # Find all .proto files
    proto_files = list(proto_dir.glob("*.proto"))
    
    if not proto_files:
        print(f"❌ No .proto files found in {proto_dir}")
        return False
    
    print(f"📁 Found {len(proto_files)} proto files:")
    for proto_file in proto_files:
        print(f"   - {proto_file.name}")
    
    # Generate Python code for each proto file
    success = True
    for proto_file in proto_files:
        print(f"\n🔨 Generating code for {proto_file.name}...")
        
        try:
            # Run protoc command
            cmd = [
                sys.executable, "-m", "grpc_tools.protoc",
                f"--proto_path={proto_dir}",
                f"--python_out={proto_dir}",
                f"--grpc_python_out={proto_dir}",
                str(proto_file)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
            
            if result.returncode == 0:
                print(f"   ✅ Successfully generated code for {proto_file.name}")
            else:
                print(f"   ❌ Failed to generate code for {proto_file.name}")
                print(f"   Error: {result.stderr}")
                success = False
                
        except Exception as e:
            print(f"   ❌ Exception while generating {proto_file.name}: {str(e)}")
            success = False
    
    if success:
        print(f"\n🎉 Successfully generated Python code for all proto files!")
        
        # List generated files
        generated_files = list(proto_dir.glob("*_pb2.py")) + list(proto_dir.glob("*_pb2_grpc.py"))
        if generated_files:
            print(f"\n📄 Generated files:")
            for gen_file in generated_files:
                print(f"   - {gen_file.name}")
        
        # Update __init__.py to import generated modules
        update_proto_init(proto_dir, [f.stem for f in proto_files])
        
    else:
        print(f"\n❌ Some proto files failed to generate. Please check the errors above.")
    
    return success

def update_proto_init(proto_dir: Path, proto_names: list):
    """Update the __init__.py file to import generated protobuf modules."""
    
    init_file = proto_dir / "__init__.py"
    
    # Generate import statements
    imports = []
    all_exports = []
    
    for proto_name in proto_names:
        pb2_module = f"{proto_name}_pb2"
        grpc_module = f"{proto_name}_pb2_grpc"
        
        imports.append(f"from . import {pb2_module}")
        imports.append(f"from . import {grpc_module}")
        
        all_exports.append(f'"{pb2_module}"')
        all_exports.append(f'"{grpc_module}"')
    
    # Create the content
    content = f'''"""
Protocol Buffer schemas for ai-workflow-automation gRPC services.

This module provides access to all gRPC service definitions and message types
used for communication between the core microservice and clients.

Generated modules are automatically imported and available for use.
"""

# Generated protobuf modules
{chr(10).join(imports)}

__all__ = [
    {f",{chr(10)}    ".join(all_exports)}
]
'''
    
    try:
        with open(init_file, 'w') as f:
            f.write(content)
        print(f"   ✅ Updated {init_file.name} with generated imports")
    except Exception as e:
        print(f"   ⚠️  Failed to update {init_file.name}: {str(e)}")

def main():
    """Main entry point."""
    print("🚀 ai-workflow-automation Protocol Buffer Code Generator")
    print("=" * 50)
    
    if generate_protos():
        print("\n✅ Protocol buffer generation completed successfully!")
        return 0
    else:
        print("\n❌ Protocol buffer generation failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 