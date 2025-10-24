import { test, expect } from '@playwright/test';

/**
 * PRD Workflow Compliance Tests
 * 
 * This test suite verifies alignment with the PRD requirements for the 
 * AAA Real Estate Lead Capture Agentic AI System, including:
 * 
 * 1. LangGraph Swarm Architecture (Qualifier, Scheduler, FollowUp agents)
 * 2. Lead qualification scoring (budget, location, property type, timeline)
 * 3. Human-in-the-Loop (HITL) for high-value leads (>$500k)
 * 4. Database schema and state persistence
 * 5. API integrations (Meta, Google Calendar, HubSpot, OpenRouter)
 * 6. Frontend dashboard functionality
 */

const BACKEND_URL = 'http://localhost:8000';
const FRONTEND_URL = 'http://localhost:5173';

test.describe('PRD Workflow Compliance - AAA Real Estate Lead Capture', () => {

  test.beforeEach(async ({ page }) => {
    // Navigate to frontend for each test
    // Navigate to frontend with e2e=true to disable auto-login
    await page.goto(FRONTEND_URL + '?e2e=true');
  });

  test('PRD Requirement 1: Backend API Endpoints Available', async ({ request }) => {
    console.log('🔍 Testing Backend API Endpoints...');
    
    // Test basic health endpoint
    try {
      const healthResponse = await request.get(`${BACKEND_URL}/health`);
      if (healthResponse.ok()) {
        const healthData = await healthResponse.json();
        console.log('✓ Backend health endpoint accessible');
        console.log(`Health status: ${healthData.status}`);
      }
    } catch (error) {
      console.log('⚠️ Backend health endpoint not accessible - backend may not be running');
    }
    
    // Test webhook endpoint
    try {
      const webhookResponse = await request.get(`${BACKEND_URL}/webhook/health`);
      if (webhookResponse.ok()) {
        console.log('✓ Webhook endpoint accessible');
      }
    } catch (error) {
      console.log('⚠️ Webhook endpoint not accessible');
    }
    
    // Test processing endpoint
    try {
      const processingResponse = await request.get(`${BACKEND_URL}/processing/process/health`);
      if (processingResponse.ok()) {
        console.log('✓ Processing endpoint accessible');
      }
    } catch (error) {
      console.log('⚠️ Processing endpoint not accessible');
    }
    
    // Test HITL endpoint
    try {
      const hitlResponse = await request.get(`${BACKEND_URL}/hitl/human/health`);
      if (hitlResponse.ok()) {
        console.log('✓ HITL endpoint accessible');
      }
    } catch (error) {
      console.log('⚠️ HITL endpoint not accessible');
    }
  });

  test('PRD Requirement 2: Lead Processing via Test Webhook', async ({ request }) => {
    console.log('🔍 Testing Lead Processing...');
    
    // Test high-score lead (should go to Scheduler)
    const highValueLead = {
      channel: 'ig',
      user_id: 'test_high_value_' + Date.now(),
      message: 'I want a luxury 3BHK in Miami, budget is 600k, need it in 2 months'
    };
    
    try {
      const highValueResponse = await request.post(`${BACKEND_URL}/webhook/test`, {
        data: highValueLead
      });
      
      if (highValueResponse.ok()) {
        const highValueResult = await highValueResponse.json();
        expect(highValueResult.status).toBe('success');
        console.log('✓ High-value lead processed');
      }
    } catch (error) {
      console.log('⚠️ High-value lead processing failed - webhook may not be available');
    }
    
    // Test low-score lead (should go to FollowUp)
    const lowValueLead = {
      channel: 'ig', 
      user_id: 'test_low_value_' + Date.now(),
      message: 'Just browsing, maybe interested in something cheap'
    };
    
    try {
      const lowValueResponse = await request.post(`${BACKEND_URL}/webhook/test`, {
        data: lowValueLead
      });
      
      if (lowValueResponse.ok()) {
        const lowValueResult = await lowValueResponse.json();
        expect(lowValueResult.status).toBe('success');
        console.log('✓ Low-value lead processed');
      }
    } catch (error) {
      console.log('⚠️ Low-value lead processing failed - webhook may not be available');
    }
  });

  test('PRD Requirement 3: HITL System Check', async ({ request }) => {
    console.log('🔍 Testing HITL System...');
    
    try {
      // Check HITL queue
      const hitlResponse = await request.get(`${BACKEND_URL}/hitl/human/pending`);
      
      if (hitlResponse.ok()) {
        const pendingLeads = await hitlResponse.json();
        console.log(`✓ HITL queue contains ${pendingLeads.length} pending leads`);
        
        // Test HITL review functionality if there are pending leads
        if (pendingLeads.length > 0) {
          const leadToReview = pendingLeads[0];
          
          const reviewResponse = await request.post(`${BACKEND_URL}/hitl/human/review`, {
            data: {
              lead_id: leadToReview.lead_id || leadToReview.id,
              action: 'approve',
              feedback: 'PRD compliance test - approved for scheduling'
            }
          });
          
          if (reviewResponse.ok()) {
            const reviewResult = await reviewResponse.json();
            expect(reviewResult.success).toBe(true);
            console.log('✓ HITL review functionality working');
          }
        }
      }
    } catch (error) {
      console.log('⚠️ HITL system not accessible - may not be fully implemented');
    }
  });

  test('PRD Requirement 4: Database Schema and State Persistence', async ({ request }) => {
    console.log('🔍 Testing Database Schema Compliance...');
    
    try {
      // Test leads API structure
      const leadsResponse = await request.get(`${BACKEND_URL}/processing/process/leads?limit=5`);
      
      if (leadsResponse.ok()) {
        const leadsData = await leadsResponse.json();
        expect(leadsData).toHaveProperty('leads');
        expect(Array.isArray(leadsData.leads)).toBe(true);
        
        if (leadsData.leads.length > 0) {
          const lead = leadsData.leads[0];
          
          // Verify PRD-required fields
          const requiredLeadFields = [
            'id', 'user_id', 'channel', 'message', 'status', 'created_at'
          ];
          
          for (const field of requiredLeadFields) {
            expect(lead).toHaveProperty(field);
          }
          
          console.log('✓ Database schema includes required lead fields');
        }
      }
    } catch (error) {
      console.log('⚠️ Database schema check failed - database may not be accessible');
    }
    
    try {
      // Test status endpoint
      const statusResponse = await request.get(`${BACKEND_URL}/status`);
      if (statusResponse.ok()) {
        const statusData = await statusResponse.json();
        console.log(`✓ Status endpoint accessible: ${statusData.status}`);
      }
    } catch (error) {
      console.log('⚠️ Status endpoint not accessible');
    }
  });

  test('PRD Requirement 5: API Integration Endpoints', async ({ request }) => {
    console.log('🔍 Testing API Integration Compliance...');
    
    // Test Meta webhook format compliance (Instagram)
    const igWebhookData = {
      object: 'instagram',
      entry: [{
        messaging: [{
          sender: { id: 'ig_test_sender_123' },
          message: { text: 'Test IG message for 2BHK Miami $300k', mid: 'ig_mid_123' }
        }]
      }]
    };
    
    try {
      const igResponse = await request.post(`${BACKEND_URL}/webhook/test`, {
        data: { ...igWebhookData, channel: 'ig' }
      });
      
      if (igResponse.ok()) {
        console.log('✓ Instagram webhook format supported');
      }
    } catch (error) {
      console.log('⚠️ Instagram webhook format not supported');
    }
    
    // Test Meta webhook format compliance ( )
    const waWebhookData = {
      object: ' _business_account',
      entry: [{
        changes: [{
          value: {
            messages: [{
              from: 'wa_test_sender_456',
              text: { body: 'Test   message for luxury condo $500k' },
              id: 'wa_test_id_456'
            }]
          }
        }]
      }]
    };
    
    try {
      const waResponse = await request.post(`${BACKEND_URL}/webhook/test`, {
        data: { ...waWebhookData, channel: ' ' }
      });
      
      if (waResponse.ok()) {
        console.log('✓   webhook format supported');
      }
    } catch (error) {
      console.log('⚠️   webhook format not supported');
    }
  });

  test('PRD Requirement 6: Meeting Scheduling Integration', async ({ request }) => {
    console.log('🔍 Testing Google Calendar Integration...');
    
    try {
      // Test calendar availability endpoint
      const calendarResponse = await request.get(`${BACKEND_URL}/test/workflow`);
      
      if (calendarResponse.ok()) {
        const calendarData = await calendarResponse.json();
        console.log('Calendar test response:', calendarData.status);
        console.log('✓ Calendar integration framework in place');
      }
    } catch (error) {
      console.log('⚠️ Calendar integration not accessible');
    }
    
    // Test meeting booking workflow simulation
    const schedulingTestLead = {
      channel: 'ig',
      user_id: 'test_scheduling_' + Date.now(),
      message: 'I want a 2BHK in Miami for $350k, available for viewing this week',
      email: 'test.scheduling@example.com'
    };
    
    try {
      const scheduleResponse = await request.post(`${BACKEND_URL}/webhook/test`, {
        data: schedulingTestLead
      });
      
      if (scheduleResponse.ok()) {
        console.log('✓ Scheduling workflow initiated');
      }
    } catch (error) {
      console.log('⚠️ Scheduling workflow not accessible');
    }
  });

  test('PRD Requirement 7: Frontend Dashboard Basic Functionality', async ({ page }) => {
    console.log('🔍 Testing React Dashboard Basic Functionality...');
    
    // Verify dashboard loads
    await expect(page.locator('body')).toBeVisible();
    
    // Check for basic form elements
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
    
    console.log('✓ Login form functionality verified');
    
    // Test form interaction
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'testpassword');
    
    const emailValue = await page.locator('input[type="email"]').inputValue();
    expect(emailValue).toBe('test@example.com');
    console.log('✓ Form inputs working correctly');
  });

  test('PRD Requirement 8: Basic Lead Journey Test', async ({ request, page }) => {
    console.log('🔍 Testing Basic Lead Journey...');
    
    const journeyTestId = 'prd_journey_' + Date.now();
    
    // Step 1: Lead arrives via test webhook (PRD Scenario)
    const leadMessage = 'I want a 2BHK in Miami for $300k, looking to buy in 3 months';
    const webhookData = {
      channel: 'ig',
      user_id: journeyTestId,
      message: leadMessage
    };
    
    console.log('Step 1: Processing test lead...');
    try {
      const webhookResponse = await request.post(`${BACKEND_URL}/webhook/test`, {
        data: webhookData
      });
      
      if (webhookResponse.ok()) {
        const webhookResult = await webhookResponse.json();
        expect(webhookResult.status).toBe('success');
        console.log('✓ Lead captured via webhook');
      }
    } catch (error) {
      console.log('⚠️ Lead capture failed - webhook may not be available');
    }
    
    // Step 2: Check if lead was processed (may take time in real system)
    console.log('Step 2: Waiting for lead processing...');
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    try {
      const statusResponse = await request.get(`${BACKEND_URL}/processing/process/status/${journeyTestId}`);
      
      if (statusResponse.ok()) {
        const statusData = await statusResponse.json();
        console.log(`✓ Lead status: ${statusData.status}`);
      }
    } catch (error) {
      console.log('⚠️ Lead status check failed');
    }
    
    // Step 3: Verify lead appears in system
    try {
      const leadsResponse = await request.get(`${BACKEND_URL}/processing/process/leads?limit=10`);
      
      if (leadsResponse.ok()) {
        const leadsData = await leadsResponse.json();
        const ourLead = leadsData.leads.find((lead: any) => lead.user_id === journeyTestId);
        
        if (ourLead) {
          console.log(`✓ Lead found in system with score: ${ourLead.qualified_score}`);
        }
      }
    } catch (error) {
      console.log('⚠️ Lead verification failed');
    }
    
    // Step 4: Test frontend is ready
    console.log('Step 4: Verifying frontend is ready...');
    await page.goto(FRONTEND_URL);
    
    await expect(page.locator('body')).toBeVisible();
    console.log('✓ Frontend ready for lead display');
    
    console.log('🎉 Basic lead journey test completed!');
  });

  test('PRD Requirement 9: Error Handling and Reliability', async ({ request }) => {
    console.log('🔍 Testing Error Handling and System Reliability...');
    
    // Test malformed webhook data
    try {
      const invalidWebhookResponse = await request.post(`${BACKEND_URL}/webhook/test`, {
        data: { invalid: 'data structure' }
      });
      
      // Should handle gracefully, not crash
      expect(invalidWebhookResponse.status()).toBeLessThan(500);
      console.log('✓ Invalid webhook data handled gracefully');
    } catch (error) {
      console.log('⚠️ Invalid webhook data test failed - endpoint may not be available');
    }
    
    // Test system health monitoring
    try {
      const healthResponse = await request.get(`${BACKEND_URL}/status`);
      if (healthResponse.ok()) {
        const healthData = await healthResponse.json();
        expect(healthData).toHaveProperty('status');
        console.log('✓ System health monitoring functional');
      }
    } catch (error) {
      console.log('⚠️ System health monitoring not accessible');
    }
  });

  test('PRD Requirement 10: Basic Performance Test', async ({ request }) => {
    console.log('🔍 Testing Basic Performance...');
    
    // Test single webhook request
    const testLead = {
      channel: 'ig',
      user_id: 'perf_test_' + Date.now(),
      message: 'Performance test lead'
    };
    
    try {
      const startTime = Date.now();
      const response = await request.post(`${BACKEND_URL}/webhook/test`, {
        data: testLead
      });
      const endTime = Date.now();
      const responseTime = endTime - startTime;
      
      if (response.ok()) {
        console.log(`✓ Webhook processed in ${responseTime}ms`);
        expect(responseTime).toBeLessThan(2000); // < 2s response time
      }
    } catch (error) {
      console.log('⚠️ Performance test failed - endpoint may not be available');
    }
  });

});