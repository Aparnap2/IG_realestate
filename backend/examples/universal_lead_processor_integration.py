"""
Universal Lead Processor Integration Examples

This module demonstrates how to integrate the Universal Lead Processing Pipeline
into existing systems, showcasing LangGraph's advanced patterns like routing,
parallel processing, orchestrator-workers, voting, and evaluator-optimizer.
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime

# Import the universal lead processor
from ..pipeline.universal_lead_processor import (
    UniversalLeadProcessor,
    universal_lead_processor,
    process_message,
    WorkflowType,
    IndustryType
)

logger = logging.getLogger(__name__)

class UniversalLeadProcessorExamples:
    """Examples demonstrating Universal Lead Processor integration"""

    def __init__(self):
        """Initialize with processor instance"""
        self.processor = universal_lead_processor

    async def example_real_estate_lead_processing(self) -> Dict[str, Any]:
        """
        Example: Real estate lead processing with LangGraph parallel assessment

        Demonstrates:
        - Industry detection (real estate)
        - Parallel assessment (scoring, engagement, booking, urgency)
        - Dynamic routing based on AI analysis
        - Orchestrator-workers response generation
        - Voting-based channel strategy
        """
        logger.info("🚀 Example: Real Estate Lead Processing")

        user_id = "example_real_estate_123"
        message = "Hi! I'm looking for a 4-bedroom house in downtown Austin with a pool. Budget is around $800k. When can we schedule a viewing?"
        user_name = "Sarah Johnson"

        # Process through universal pipeline
        result = await process_message(
            user_id=user_id,
            message=message,
            channel="instagram",
            user_name=user_name
        )

        logger.info(f"✅ Processing Result: {result['status']}")
        logger.info(f"🏭 Detected Industry: {result.get('industry_type', 'unknown')}")
        logger.info(f"🎯 Workflow: {result.get('workflow_type', 'unknown')}")
        logger.info(f"📊 Readiness Score: {result.get('readiness_assessment', {}).get('readiness_score', 0):.3f}")
        logger.info(f"💬 Response: {result.get('response_message', '')[:100]}...")

        return result

    async def example_fitness_lead_processing(self) -> Dict[str, Any]:
        """
        Example: Fitness industry lead processing

        Demonstrates:
        - Industry detection (fitness)
        - Parallel assessment with industry-specific factors
        - Dynamic routing for service-based business
        - Compliance checking for fitness industry
        """
        logger.info("💪 Example: Fitness Lead Processing")

        user_id = "example_fitness_456"
        message = "I want to join your gym and get a personal trainer. I'm 35 years old, work out 2-3 times a week, and have some knee issues."
        user_name = "Mike Chen"

        result = await process_message(
            user_id=user_id,
            message=message,
            channel="instagram",
            user_name=user_name
        )

        logger.info(f"✅ Processing Result: {result['status']}")
        logger.info(f"🏭 Detected Industry: {result.get('industry_type', 'unknown')}")
        logger.info(f"🎯 Workflow: {result.get('workflow_type', 'unknown')}")

        return result

    async def example_restaurant_lead_processing(self) -> Dict[str, Any]:
        """
        Example: Restaurant industry lead processing

        Demonstrates:
        - Industry detection (restaurant)
        - Time-sensitive booking workflows
        - Multi-party consideration
        - Channel optimization for immediate response
        """
        logger.info("🍽️ Example: Restaurant Lead Processing")

        user_id = "example_restaurant_789"
        message = "Table for 4 tonight at 7pm? We're celebrating my wife's birthday. Any window seats available?"
        user_name = "David Rodriguez"

        result = await process_message(
            user_id=user_id,
            message=message,
            channel="instagram",
            user_name=user_name
        )

        logger.info(f"✅ Processing Result: {result['status']}")
        logger.info(f"🏭 Detected Industry: {result.get('industry_type', 'unknown')}")
        logger.info(f"🎯 Workflow: {result.get('workflow_type', 'unknown')}")

        return result

    async def example_hotel_lead_processing(self) -> Dict[str, Any]:
        """
        Example: Hotel industry lead processing

        Demonstrates:
        - Industry detection (hotel)
        - Date-specific booking logic
        - Multi-factor assessment for group bookings
        - Compliance with hospitality regulations
        """
        logger.info("🏨 Example: Hotel Lead Processing")

        user_id = "example_hotel_101"
        message = "Need 2 rooms for 3 nights next weekend. King beds, pool view, and free breakfast included?"
        user_name = "Jennifer Smith"

        result = await process_message(
            user_id=user_id,
            message=message,
            channel="instagram",
            user_name=user_name
        )

        logger.info(f"✅ Processing Result: {result['status']}")
        logger.info(f"🏭 Detected Industry: {result.get('industry_type', 'unknown')}")
        logger.info(f"🎯 Workflow: {result.get('workflow_type', 'unknown')}")

        return result

    async def example_langgraph_patterns_demonstration(self) -> Dict[str, Any]:
        """
        Example: Demonstrating all LangGraph patterns in action

        This example shows how the Universal Lead Processor leverages:
        1. Parallelization (Sectioning): Multiple assessment tasks run simultaneously
        2. Routing: AI-powered dynamic workflow selection
        3. Orchestrator-Workers: Response generation with specialized workers
        4. Voting: Channel strategy determination from multiple perspectives
        5. Evaluator-Optimizer: Workflow execution with continuous evaluation
        """
        logger.info("🎭 Example: LangGraph Patterns Demonstration")

        # Complex lead that will trigger multiple patterns
        user_id = "complex_lead_demo"
        message = """Hi there! I'm looking for a commercial space to open a fitness studio.
        I need about 2000 sq ft, good location with parking, budget around $300k.
        I'm very serious about moving forward quickly - can we schedule a tour this week?
        Also, I have questions about zoning, permits, and lease terms."""
        user_name = "Alex Thompson"

        # Process through universal pipeline
        result = await process_message(
            user_id=user_id,
            message=message,
            channel="instagram",
            user_name=user_name
        )

        # Analyze the patterns used
        patterns_used = result.get('langgraph_used', False)
        if patterns_used:
            logger.info("🎭 LangGraph Patterns Successfully Applied:")
            logger.info("  ✅ Parallelization: Multiple assessments ran simultaneously")
            logger.info("  ✅ Routing: AI determined optimal workflow")
            logger.info("  ✅ Orchestrator-Workers: Response generated by specialized workers")
            logger.info("  ✅ Voting: Channel strategy selected by consensus")
            logger.info("  ✅ Evaluator-Optimizer: Workflow execution evaluated and optimized")

        return result

    async def example_error_handling_and_fallback(self) -> Dict[str, Any]:
        """
        Example: Error handling and fallback mechanisms

        Demonstrates:
        - Graceful degradation when LangGraph is unavailable
        - Fallback to traditional processing logic
        - Error recovery and production processor fallback
        """
        logger.info("🛡️ Example: Error Handling and Fallback")

        # Simulate LangGraph unavailability
        original_langgraph_available = hasattr(self.processor, '_UniversalLeadProcessor__langgraph_available')
        if original_langgraph_available:
            # Temporarily disable LangGraph
            self.processor._UniversalLeadProcessor__langgraph_available = False

        try:
            user_id = "error_handling_test"
            message = "Looking for real estate investment opportunities"
            user_name = "Error Test User"

            result = await process_message(
                user_id=user_id,
                message=message,
                channel="instagram",
                user_name=user_name
            )

            logger.info(f"✅ Fallback Processing Result: {result['status']}")
            logger.info(f"🔄 Fallback Used: {result.get('fallback_result') is not None}")

        finally:
            # Restore original state
            if original_langgraph_available:
                self.processor._UniversalLeadProcessor__langgraph_available = True

        return result

    async def example_performance_comparison(self) -> List[Dict[str, Any]]:
        """
        Example: Performance comparison between LangGraph and traditional processing

        Demonstrates the efficiency gains from parallel processing and AI routing.
        """
        logger.info("⚡ Example: Performance Comparison")

        test_cases = [
            {
                "user_id": "perf_test_1",
                "message": "Simple inquiry about property listings",
                "user_name": "Simple User",
                "expected_complexity": "low"
            },
            {
                "user_id": "perf_test_2",
                "message": "Complex commercial real estate investment with multiple properties, financing questions, and urgent timeline",
                "user_name": "Complex User",
                "expected_complexity": "high"
            }
        ]

        results = []

        for test_case in test_cases:
            logger.info(f"Testing: {test_case['expected_complexity']} complexity")

            start_time = datetime.now()
            result = await process_message(
                user_id=test_case["user_id"],
                message=test_case["message"],
                channel="instagram",
                user_name=test_case["user_name"]
            )
            end_time = datetime.now()

            processing_time = (end_time - start_time).total_seconds()

            result["processing_time"] = processing_time
            result["complexity"] = test_case["expected_complexity"]
            result["langgraph_used"] = result.get("langgraph_used", False)

            results.append(result)

            logger.info(".3f")
            logger.info(f"  LangGraph Used: {result['langgraph_used']}")

        return results

    async def example_industry_adaptive_responses(self) -> Dict[str, Any]:
        """
        Example: Industry-adaptive response generation

        Demonstrates how responses are tailored to different industries
        while maintaining consistent quality and conversion focus.
        """
        logger.info("🎨 Example: Industry-Adaptive Responses")

        test_cases = [
            {
                "industry": "real_estate",
                "user_id": "adaptive_test_re",
                "message": "Looking for a family home",
                "user_name": "Real Estate Buyer"
            },
            {
                "industry": "fitness",
                "user_id": "adaptive_test_fitness",
                "message": "Want to get in shape",
                "user_name": "Fitness Enthusiast"
            },
            {
                "industry": "restaurant",
                "message": "Hungry for Italian food",
                "user_name": "Restaurant Guest"
            },
            {
                "industry": "hotel",
                "user_id": "adaptive_test_hotel",
                "message": "Need a place to stay",
                "user_name": "Hotel Guest"
            }
        ]

        results = {}

        for test_case in test_cases:
            logger.info(f"Generating response for {test_case['industry']} industry")

            result = await process_message(
                user_id=test_case["user_id"],
                message=test_case["message"],
                channel="instagram",
                user_name=test_case["user_name"]
            )

            results[test_case["industry"]] = {
                "response": result.get("response_message", ""),
                "workflow": result.get("workflow_type", ""),
                "industry_detected": result.get("industry_type", "")
            }

            logger.info(f"  Response: {result.get('response_message', '')[:80]}...")

        return results

async def run_examples():
    """Run all integration examples"""
    logger.info("🚀 Running Universal Lead Processor Integration Examples")

    examples = UniversalLeadProcessorExamples()

    # Run individual examples
    try:
        # Basic industry examples
        await examples.example_real_estate_lead_processing()
        await examples.example_fitness_lead_processing()
        await examples.example_restaurant_lead_processing()
        await examples.example_hotel_lead_processing()

        # Advanced pattern demonstration
        await examples.example_langgraph_patterns_demonstration()

        # Error handling
        await examples.example_error_handling_and_fallback()

        # Performance comparison
        perf_results = await examples.example_performance_comparison()

        # Industry adaptation
        adaptive_results = await examples.example_industry_adaptive_responses()

        logger.info("✅ All integration examples completed successfully")

        return {
            "performance_results": perf_results,
            "adaptive_results": adaptive_results,
            "status": "success"
        }

    except Exception as e:
        logger.error(f"❌ Error running examples: {e}")
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run examples
    asyncio.run(run_examples())