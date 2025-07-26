#!/usr/bin/env python3
"""
Main Workflow Controller for Foxtons Property Scraping
Orchestrates all steps of the scraping process in the correct order.
"""

import os
import sys
import time
from datetime import datetime

def run_step(step_name, module_name, function_name=None):
    """Run a single step of the workflow"""
    print(f"\n{'='*60}")
    print(f"🚀 STEP: {step_name}")
    print(f"{'='*60}")
    start_time = time.time()
    
    try:
        if function_name:
            # Import and run specific function
            module = __import__(module_name)
            func = getattr(module, function_name)
            result = func()
        else:
            # Run module as main
            os.system(f"python {module_name}.py")
            result = True
        
        end_time = time.time()
        duration = end_time - start_time
        
        if result:
            print(f"✅ {step_name} completed successfully in {duration:.2f} seconds")
            return True
        else:
            print(f"❌ {step_name} failed after {duration:.2f} seconds")
            return False
            
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"❌ {step_name} failed with error after {duration:.2f} seconds: {str(e)}")
        return False

def run_complete_workflow():
    """Run the complete workflow from start to finish"""
    print("🏠 FOXTONS PROPERTY SCRAPING WORKFLOW")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    workflow_start_time = time.time()
    
    # Step 1: Initial URLs Collection
    if not run_step("Initial URLs Collection", "initial_urls_collection", "main"):
        print("❌ Workflow stopped due to failure in Step 1")
        return False
    
    # Step 2: Secondary URLs Collection  
    if not run_step("Secondary URLs Collection", "secondary_urls_collection"):
        print("❌ Workflow stopped due to failure in Step 2")
        return False
    
    # Step 3: Check Existing Listings (NEW STEP)
    if not run_step("Check Existing Listings", "check_existing_listings"):
        print("❌ Workflow stopped due to failure in Step 3")
        return False
    
    # Step 4: Listing Details Scraping
    if not run_step("Listing Details Scraping", "listing_details"):
        print("❌ Workflow stopped due to failure in Step 4")
        return False
    
    # Step 5: Update Listings via Direct DB (Optional)
    print(f"\n{'='*60}")
    print("🔧 OPTIONAL: Direct Database Updates")
    print(f"{'='*60}")
    print("You can run update_listings_pymssql.py manually if needed for direct DB updates")
    
    workflow_end_time = time.time()
    total_duration = workflow_end_time - workflow_start_time
    
    print(f"\n{'='*60}")
    print("🎉 WORKFLOW COMPLETED SUCCESSFULLY!")
    print(f"{'='*60}")
    print(f"Total time: {total_duration:.2f} seconds ({total_duration/60:.1f} minutes)")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return True

def run_individual_step():
    """Run individual steps based on user choice"""
    steps = {
        "1": ("Initial URLs Collection", "initial_urls_collection", "main"),
        "2": ("Secondary URLs Collection", "secondary_urls_collection", None),
        "3": ("Check Existing Listings", "check_existing_listings", None),
        "4": ("Listing Details Scraping", "listing_details", None),
        "5": ("Update Listings (Direct DB)", "update_listings_pymssql", None)
    }
    
    print("🏠 FOXTONS PROPERTY SCRAPING - INDIVIDUAL STEPS")
    print("=" * 60)
    print("Available steps:")
    for key, (name, _, _) in steps.items():
        print(f"  {key}. {name}")
    
    choice = input("\nEnter step number (1-5): ").strip()
    
    if choice in steps:
        name, module, function = steps[choice]
        run_step(name, module, function)
    else:
        print("❌ Invalid choice")

def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg == "complete" or arg == "all":
            run_complete_workflow()
        elif arg == "step" or arg == "individual":
            run_individual_step()
        elif arg == "1":
            run_step("Initial URLs Collection", "initial_urls_collection", "main")
        elif arg == "2":
            run_step("Secondary URLs Collection", "secondary_urls_collection")
        elif arg == "3":
            run_step("Check Existing Listings", "check_existing_listings")
        elif arg == "4":
            run_step("Listing Details Scraping", "listing_details")
        elif arg == "5":
            run_step("Update Listings (Direct DB)", "update_listings_pymssql")
        else:
            print("❌ Unknown argument. Use: complete, step, or 1-5")
    else:
        print("🏠 FOXTONS PROPERTY SCRAPING")
        print("=" * 60)
        print("Usage:")
        print("  python main.py complete    - Run complete workflow")
        print("  python main.py step        - Choose individual step")
        print("  python main.py 1           - Run step 1 only")
        print("  python main.py 2           - Run step 2 only")  
        print("  python main.py 3           - Run step 3 only (NEW)")
        print("  python main.py 4           - Run step 4 only")
        print("  python main.py 5           - Run step 5 only")
        print("\nStep 3 is the NEW existing listings checker!")

if __name__ == "__main__":
    main()  