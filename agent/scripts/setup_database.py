# #!/usr/bin/env python3
# """
# Database Setup Script for ai-workflow-automation Core

# This script sets up the initial database schema in Supabase.
# Run this after updating your .env file with Supabase credentials.
# """

# import asyncio
# import os
# import sys
# from pathlib import Path

# # Add the app directory to Python path
# current_dir = Path(__file__).parent
# core_dir = current_dir.parent
# app_dir = core_dir / "app"
# sys.path.insert(0, str(app_dir))

# from app.shared.config import get_settings
# from supabase import create_client, Client


# async def setup_database():
#     """Set up the database schema in Supabase"""
    
#     print("🚀 Setting up ai-workflow-automation database schema...")
    
#     # Load configuration
#     settings = get_settings()
    
#     print(f"📡 Connecting to Supabase: {settings.supabase.url}")
    
#     # Create Supabase client with service role key for admin operations
#     service_key = settings.supabase.service_role_key or settings.supabase.api_key
#     supabase: Client = create_client(
#         settings.supabase.url,
#         service_key
#     )
    
#     # Read the migration file
#     migration_file = core_dir / "database" / "migrations" / "001_initial_schema.sql"
    
#     if not migration_file.exists():
#         print(f"❌ Migration file not found: {migration_file}")
#         return False
    
#     print(f"📖 Reading migration file: {migration_file}")
    
#     with open(migration_file, 'r') as f:
#         migration_sql = f.read()
    
#     # Split the migration into individual statements
#     # This is needed because some PostgreSQL extensions need to be run separately
#     statements = [
#         stmt.strip() 
#         for stmt in migration_sql.split(';') 
#         if stmt.strip() and not stmt.strip().startswith('--')
#     ]
    
#     print(f"🔧 Executing {len(statements)} SQL statements...")
    
#     success_count = 0
#     error_count = 0
    
#     for i, statement in enumerate(statements, 1):
#         try:
#             # Execute each statement
#             if statement.strip():
#                 print(f"  [{i}/{len(statements)}] Executing statement...")
                
#                 # Use Supabase's SQL execution method
#                 result = supabase.postgrest.rpc('sql', {
#                     'query': statement + ';'
#                 }).execute()
                
#                 success_count += 1
                
#         except Exception as e:
#             error_count += 1
#             print(f"  ⚠️  Error in statement {i}: {str(e)}")
            
#             # Some errors might be expected (like "already exists")
#             if any(phrase in str(e).lower() for phrase in [
#                 'already exists', 
#                 'duplicate', 
#                 'constraint already exists'
#             ]):
#                 print(f"     (This is likely OK - resource already exists)")
#                 success_count += 1
#                 error_count -= 1
#             else:
#                 print(f"     Statement: {statement[:100]}...")
    
#     print(f"\n✅ Database setup completed!")
#     print(f"   📊 Successful statements: {success_count}")
#     print(f"   ❌ Failed statements: {error_count}")
    
#     if error_count == 0:
#         print(f"🎉 All database migrations applied successfully!")
        
#         # Test the connection by querying a table
#         try:
#             result = supabase.table('schema_migrations').select('*').execute()
#             print(f"🔍 Schema version check: {len(result.data)} migration(s) applied")
            
#             # Try to query MCP tools to verify the setup
#             tools_result = supabase.table('mcp_tools').select('name, server_name').execute()
#             print(f"🛠️  Available MCP tools: {len(tools_result.data)} tools registered")
            
#         except Exception as e:
#             print(f"⚠️  Warning: Could not verify database setup: {str(e)}")
    
#     return error_count == 0


# def check_environment():
#     """Check if environment is properly configured"""
#     print("🔍 Checking environment configuration...")
    
#     required_vars = [
#         'SUPABASE_URL',
#         'SUPABASE_API_KEY'
#     ]
    
#     # Check for service role key (preferred for admin operations)
#     if not os.getenv('SUPABASE_SERVICE_ROLE_KEY'):
#         print("⚠️  Warning: SUPABASE_SERVICE_ROLE_KEY not found.")
#         print("   Using SUPABASE_API_KEY, but this may have limited permissions.")
#         print("   For full database setup, please use the service role key.")
    
#     missing_vars = []
#     for var in required_vars:
#         if not os.getenv(var):
#             missing_vars.append(var)
    
#     if missing_vars:
#         print(f"❌ Missing required environment variables:")
#         for var in missing_vars:
#             print(f"   - {var}")
#         print(f"\n💡 Please update your .env file with these values.")
#         return False
    
#     print("✅ Environment configuration looks good!")
#     return True


# async def main():
#     """Main setup function"""
#     print("🌟 ai-workflow-automation Database Setup")
#     print("=" * 50)
    
#     # Check environment first
#     if not check_environment():
#         sys.exit(1)
    
#     # Set up database
#     success = await setup_database()
    
#     if success:
#         print("\n🎉 Database setup completed successfully!")
#         print("\n📝 Next steps:")
#         print("   1. Start the ai-workflow-automation core service: python -m app.main")
#         print("   2. Check health endpoint: http://localhost:8080/health/")
#         print("   3. View API docs: http://localhost:8080/docs")
#     else:
#         print("\n❌ Database setup failed. Please check the errors above.")
#         sys.exit(1)


# if __name__ == "__main__":
#     asyncio.run(main()) 