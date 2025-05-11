# check_sip_config.py
import asyncio
import os
from dotenv import load_dotenv
from livekit.api import LiveKitAPI, ListSIPTrunkRequest, CreateSIPTrunkRequest

load_dotenv()

async def check_sip_configuration():
    try:
        # Initialize LiveKit API client
        url = f"https://{os.getenv('LIVEKIT_URL')}"
        api_key = os.getenv('LIVEKIT_API_KEY')
        api_secret = os.getenv('LIVEKIT_API_SECRET')
        
        print(f"Connecting to: {url}")
        
        livekit_api = LiveKitAPI(url, api_key, api_secret)
        
        # List existing SIP trunks
        print("\n1. Checking existing SIP trunks...")
        list_request = ListSIPTrunkRequest()
        response = await livekit_api.sip.list_sip_trunk(list_request)
        
        if response.items:
            print(f"Found {len(response.items)} SIP trunk(s):")
            for trunk in response.items:
                print(f"  - ID: {trunk.sip_trunk_id}")
                print(f"    Name: {trunk.name}")
                print(f"    Created: {trunk.created_at}")
                print(f"    Inbound: {trunk.inbound}")
                print(f"    Outbound: {trunk.outbound}")
                print("    ---")
        else:
            print("No SIP trunks found!")
            
            # Ask if user wants to create one
            create = input("\nWould you like to create a new SIP trunk? (y/n): ")
            if create.lower() == 'y':
                await create_sip_trunk(livekit_api)
        
    except Exception as e:
        print(f"Error checking SIP configuration: {e}")
        print(f"Error type: {type(e).__name__}")

async def create_sip_trunk(livekit_api):
    """Create a new SIP trunk"""
    try:
        from livekit.api import (
            CreateSIPTrunkRequest, 
            SIPTrunkInfo,
            SIPTrunkInbound,
            SIPTrunkOutbound
        )
        
        # Create inbound configuration
        inbound = SIPTrunkInbound(
            allowed_addresses=["*"],  # Allow all addresses for testing
            allowed_numbers=["+*"],   # Allow all numbers for testing
            # Uncomment if you want specific room routing
            # routing_rule={
            #     "type": "join_room",
            #     "action": {
            #         "room": "salon-reception",
            #         "pin": "optional_pin"
            #     }
            # }
        )
        
        # Create outbound configuration
        outbound = SIPTrunkOutbound(
            display_name="Elegant Touch Salon",
            allowed_addresses=["*"],
            allowed_numbers=["+*"]
        )
        
        # Create the trunk request
        trunk_request = CreateSIPTrunkRequest(
            name="AI Receptionist SIP Trunk",
            inbound=inbound,
            outbound=outbound,
            metadata="AI Receptionist for Elegant Touch Salon"
        )
        
        print("\nCreating new SIP trunk...")
        response = await livekit_api.sip.create_sip_trunk(trunk_request)
        
        print(f"SIP trunk created successfully!")
        print(f"ID: {response.sip_trunk_id}")
        print(f"Name: {response.name}")
        
        # Save to configuration file
        save_config = input("\nSave this configuration to your data folder? (y/n): ")
        if save_config.lower() == 'y':
            import json
            config = {
                "id": response.sip_trunk_id,
                "name": response.name,
                "created_at": response.created_at,
                "inbound": {
                    "allowed_addresses": inbound.allowed_addresses,
                    "allowed_numbers": inbound.allowed_numbers
                },
                "outbound": {
                    "display_name": outbound.display_name,
                    "allowed_addresses": outbound.allowed_addresses,
                    "allowed_numbers": outbound.allowed_numbers
                }
            }
            
            os.makedirs("backend/data", exist_ok=True)
            with open("backend/data/sip_trunk_config.json", "w") as f:
                json.dump(config, f, indent=2)
            
            print("Configuration saved to backend/data/sip_trunk_config.json")
        
    except Exception as e:
        print(f"Error creating SIP trunk: {e}")

if __name__ == "__main__":
    asyncio.run(check_sip_configuration())