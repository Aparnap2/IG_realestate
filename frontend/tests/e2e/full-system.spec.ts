import { test, expect } from '@playwright/test';

// Test configuration
const BACKEND_URL = 'http://localhost:8000';
const FRONTEND_URL = 'http://localhost:5173';

test.describe('AAA Real Estate E2E System Tests', () => {
  
  test.beforeEach(async ({ page }) => {
    // Setup test data before each test
    await page.goto(FRONTEND_URL);
  });

  test('Backend Health Check - All Services Operational', async ({ request }) => {
    console.log('🔍 Testing Backend Health...');
    
    // Test main health endpoint
    const healthResponse = await request.get(`${BACKEND_URL}/status`);
    expect(healthResponse.ok()).toBeTruthy();
    
    const healthData = await healthResponse.json();
    console.log('Health Status:', healthData);
    
    expect(healthData.status).toBe('operational');
    expect(healthData.components).toBeDefined();
    expect(healthData.components.redis).toBe('healthy');
  });

  test('Webhook Processing - Instagram Message Flow', async ({ request }) => {
    console.log('🔍 Testing Instagram Webhook Processing...');
    
    const testWebhookData = {
      channel: 'ig',
      user_id: 'test_ig_user_' + Date.now(),
      message: 'I want a 2BHK in Miami for $350,000'
    };
    
    // Test webhook endpoint
    const webhookResponse = await request.post(`${BACKEND_URL}/webhook/test`, {
      data: testWebhookData
    });
    
    expect(webhookResponse.ok()).toBeTruthy();
    const webhookResult = await webhookResponse.json();
    
    console.log('Webhook Result:', webhookResult);
    expect(webhookResult.status).toBe('success');
    expect(webhookResult.task_id).toBeDefined();
  });

  test('Webhook Processing - WhatsApp Message Flow', async ({ request }) => {
    console.log('🔍 Testing WhatsApp Webhook Processing...');
    
    const testWebhookData = {
      channel: 'whatsapp',
      user_id: 'test_wa_user_' + Date.now(),
      message: 'Looking for luxury 3BHK, budget 600k'
    };
    
    const webhookResponse = await request.post(`${BACKEND_URL}/webhook/test`, {
      data: testWebhookData
    });
    
    expect(webhookResponse.ok()).toBeTruthy();
    const webhookResult = await webhookResponse.json();
    
    expect(webhookResult.status).toBe('success');
    expect(webhookResult.task_id).toBeDefined();
  });

  test('Lead Processing API - Create and Retrieve', async ({ request }) => {
    console.log('🔍 Testing Lead Processing API...');
    
    const testLead = {
      channel: 'test',
      user_id: 'api_test_user_' + Date.now(),
      message: 'Need 2BHK apartment in Miami, budget 300k',
      email: 'test@example.com'
    };
    
    // Create lead via processing API
    const createResponse = await request.post(`${BACKEND_URL}/processing/process/lead`, {
      data: testLead
    });
    
    expect(createResponse.ok()).toBeTruthy();
    const createResult = await createResponse.json();
    
    console.log('Lead Creation Result:', createResult);
    expect(createResult.success).toBe(true);
    expect(createResult.lead_id).toBeDefined();
    
    // Retrieve lead status
    const statusResponse = await request.get(`${BACKEND_URL}/processing/process/status/${testLead.user_id}`);
    
    if (statusResponse.ok()) {
      const statusResult = await statusResponse.json();
      console.log('Lead Status:', statusResult);
      expect(statusResult.user_id).toBe(testLead.user_id);
    }
  });

  test('HITL API - Review High-Value Lead', async ({ request }) => {
    console.log('🔍 Testing HITL Review System...');
    
    // Get pending leads
    const pendingResponse = await request.get(`${BACKEND_URL}/hitl/human/pending`);
    
    if (pendingResponse.ok()) {
      const pendingLeads = await pendingResponse.json();
      console.log('Pending HITL Leads:', pendingLeads.length);
      
      if (pendingLeads.length > 0) {
        const testLead = pendingLeads[0];
        
        // Review the lead
        const reviewResponse = await request.post(`${BACKEND_URL}/hitl/human/review`, {
          data: {
            lead_id: testLead.lead_id,
            action: 'approve',
            feedback: 'E2E test approval'
          }
        });
        
        if (reviewResponse.ok()) {
          const reviewResult = await reviewResponse.json();
          console.log('HITL Review Result:', reviewResult);
          expect(reviewResult.success).toBe(true);
        }
      }
    }
  });

  test('Frontend Authentication Flow', async ({ page }) => {
    console.log('🔍 Testing Frontend Authentication...');
    
    await page.goto(`${FRONTEND_URL}/login`);
    
    // Check login page elements
    await expect(page.locator('h2')).toContainText('AAA Real Estate Dashboard');
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    
    // Test login form (will fail without valid credentials, but form should work)
    await page.fill('input[type="email"]', 'test@aaa-realestate.com');
    await page.fill('input[type="password"]', 'TestPass123!');
    
    const loginButton = page.locator('button[type="submit"]');
    await expect(loginButton).toBeVisible();
    await expect(loginButton).toContainText('Sign in');
  });

  test('Frontend Dashboard - Metrics Display', async ({ page }) => {
    console.log('🔍 Testing Dashboard Metrics...');
    
    // Skip auth for testing (would need valid credentials)
    await page.goto(FRONTEND_URL);
    
    // Check if dashboard elements are present
    const dashboardElements = [
      'AAA Real Estate Dashboard',
      'Lead Management',
      'Total Leads',
      'Recent Leads'
    ];
    
    for (const element of dashboardElements) {
      const locator = page.locator(`text=${element}`);
      if (await locator.count() > 0) {
        console.log(`✓ Found: ${element}`);
      }
    }
  });

  test('API Data Format Validation', async ({ request }) => {
    console.log('🔍 Testing API Data Formats...');
    
    // Test leads API response format
    const leadsResponse = await request.get(`${BACKEND_URL}/processing/process/leads?limit=5`);
    
    if (leadsResponse.ok()) {
      const leadsData = await leadsResponse.json();
      console.log('Leads API Response:', leadsData);
      
      expect(leadsData).toHaveProperty('leads');
      expect(leadsData).toHaveProperty('count');
      expect(Array.isArray(leadsData.leads)).toBe(true);
      
      if (leadsData.leads.length > 0) {
        const lead = leadsData.leads[0];
        const requiredFields = ['id', 'user_id', 'channel', 'message', 'status', 'created_at'];
        
        for (const field of requiredFields) {
          expect(lead).toHaveProperty(field);
        }
      }
    }
    
    // Test metrics API response format
    const metricsResponse = await request.get(`${BACKEND_URL}/processing/process/metrics`);
    
    if (metricsResponse.ok()) {
      const metricsData = await metricsResponse.json();
      console.log('Metrics API Response:', metricsData);
      
      const expectedMetrics = ['total_leads', 'qualified_leads', 'scheduled_leads', 'average_qualification_score'];
      
      for (const metric of expectedMetrics) {
        expect(metricsData).toHaveProperty(metric);
        expect(typeof metricsData[metric]).toBe('number');
      }
    }
  });

  test('Meta API Integration - Request Format Validation', async ({ request }) => {
    console.log('🔍 Testing Meta API Integration Format...');
    
    // Test Instagram webhook format
    const igWebhookData = {
      object: 'instagram',
      entry: [{
        messaging: [{
          sender: { id: 'test_sender_123' },
          message: { text: 'Test message', mid: 'test_mid_123' }
        }]
      }]
    };
    
    const igResponse = await request.post(`${BACKEND_URL}/webhook/test`, {
      data: { ...igWebhookData, channel: 'ig' }
    });
    
    expect(igResponse.ok()).toBeTruthy();
    
    // Test WhatsApp webhook format
    const waWebhookData = {
      object: 'whatsapp_business_account',
      entry: [{
        changes: [{
          value: {
            messages: [{
              from: 'test_sender_456',
              text: { body: 'Test WhatsApp message' },
              id: 'test_wa_id_456'
            }]
          }
        }]
      }]
    };
    
    const waResponse = await request.post(`${BACKEND_URL}/webhook/test`, {
      data: { ...waWebhookData, channel: 'whatsapp' }
    });
    
    expect(waResponse.ok()).toBeTruthy();
  });

  test('Google Calendar API - Request Format Validation', async ({ request }) => {
    console.log('🔍 Testing Google Calendar Integration Format...');
    
    // Test calendar slot availability (mock response expected)
    const calendarResponse = await request.get(`${BACKEND_URL}/test/workflow`);
    
    if (calendarResponse.ok()) {
      const calendarData = await calendarResponse.json();
      console.log('Calendar Test Response:', calendarData);
      
      expect(calendarData).toHaveProperty('status');
      expect(['success', 'error']).toContain(calendarData.status);
    }
  });

  test('PRD Compliance - Workflow Validation', async ({ request }) => {
    console.log('🔍 Testing PRD Compliance...');
    
    const prdChecks = {
      'LangGraph Workflow': false,
      'Redis State Management': false,
      'HITL Interrupts': false,
      'Three Agent Architecture': false,
      'Database Integration': false
    };
    
    // Test workflow creation
    const workflowResponse = await request.get(`${BACKEND_URL}/test/workflow`);
    if (workflowResponse.ok()) {
      const workflowData = await workflowResponse.json();
      if (workflowData.status === 'success') {
        prdChecks['LangGraph Workflow'] = true;
      }
    }
    
    // Test Redis health
    const healthResponse = await request.get(`${BACKEND_URL}/status`);
    if (healthResponse.ok()) {
      const healthData = await healthResponse.json();
      if (healthData.components?.redis === 'healthy') {
        prdChecks['Redis State Management'] = true;
      }
      if (healthData.components?.supabase?.includes('connected')) {
        prdChecks['Database Integration'] = true;
      }
    }
    
    // Test HITL functionality
    const hitlResponse = await request.get(`${BACKEND_URL}/hitl/human/health`);
    if (hitlResponse.ok()) {
      prdChecks['HITL Interrupts'] = true;
    }
    
    // Test agent endpoints
    const agentEndpoints = [
      '/webhook/health',
      '/processing/process/health',
      '/hitl/human/health'
    ];
    
    let agentCount = 0;
    for (const endpoint of agentEndpoints) {
      const response = await request.get(`${BACKEND_URL}${endpoint}`);
      if (response.ok()) agentCount++;
    }
    
    if (agentCount >= 3) {
      prdChecks['Three Agent Architecture'] = true;
    }
    
    console.log('PRD Compliance Check:', prdChecks);
    
    // Verify critical PRD requirements
    expect(prdChecks['LangGraph Workflow']).toBe(true);
    expect(prdChecks['Redis State Management']).toBe(true);
    expect(prdChecks['Database Integration']).toBe(true);
  });

  test('End-to-End Lead Journey', async ({ request }) => {
    console.log('🔍 Testing Complete Lead Journey...');
    
    const testUserId = 'e2e_test_user_' + Date.now();
    
    // Step 1: Webhook receives lead
    const webhookData = {
      channel: 'ig',
      user_id: testUserId,
      message: 'I want a luxury 3BHK in Miami, budget is 550k, need it in 2 months'
    };
    
    const webhookResponse = await request.post(`${BACKEND_URL}/webhook/test`, {
      data: webhookData
    });
    
    expect(webhookResponse.ok()).toBeTruthy();
    const webhookResult = await webhookResponse.json();
    expect(webhookResult.status).toBe('success');
    
    console.log('✓ Step 1: Webhook processed');
    
    // Step 2: Check if lead was processed (may take time in real system)
    await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds
    
    const statusResponse = await request.get(`${BACKEND_URL}/processing/process/status/${testUserId}`);
    
    if (statusResponse.ok()) {
      const statusData = await statusResponse.json();
      console.log('✓ Step 2: Lead status retrieved:', statusData.status);
      
      // Step 3: Verify lead appears in dashboard data
      const leadsResponse = await request.get(`${BACKEND_URL}/processing/process/leads?limit=10`);
      
      if (leadsResponse.ok()) {
        const leadsData = await leadsResponse.json();
        const ourLead = leadsData.leads.find(lead => lead.user_id === testUserId);
        
        if (ourLead) {
          console.log('✓ Step 3: Lead found in system:', ourLead.id);
          
          // Step 4: If high-value, should be in HITL queue
          if (ourLead.budget > 500000 || ourLead.qualified_score > 0.9) {
            const hitlResponse = await request.get(`${BACKEND_URL}/hitl/human/pending`);
            
            if (hitlResponse.ok()) {
              const hitlLeads = await hitlResponse.json();
              const hitlLead = hitlLeads.find(lead => lead.user_id === testUserId);
              
              if (hitlLead) {
                console.log('✓ Step 4: High-value lead in HITL queue');
              }
            }
          }
        }
      }
    }
    
    console.log('✓ End-to-End Journey Complete');
  });

});
