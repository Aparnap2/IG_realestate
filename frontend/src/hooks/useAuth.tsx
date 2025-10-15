import { createContext, useContext, useEffect, useState } from 'react'
import { User } from '@supabase/supabase-js'
import { supabase } from '../lib/supabaseClient'

interface AuthContextType {
  user: User | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Check if we're in E2E testing mode - don't auto-login
    const isE2ETesting = window.location.search.includes('e2e=true') ||
                        process.env.NODE_ENV === 'test' ||
                        localStorage.getItem('e2e_testing') === 'true';
    
    if (!isE2ETesting) {
      // TEMPORARY: Auto-login for development (not testing)
      const mockUser = {
        id: 'dev-user-123',
        email: 'dev@test.com',
        user_metadata: { name: 'Dev User' }
      }
      setUser(mockUser as any)
      setLoading(false)
      return
    }
    
    // For E2E testing, don't auto-login
    setLoading(false)
    
    /* RESTORE THIS WHEN AUTH IS READY
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null)
      setLoading(false)
    })
    */

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setUser(session?.user ?? null)
        setLoading(false)
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  const signIn = async (email: string, password: string) => {
    // TEMPORARY DEV BYPASS - Remove in production
    if (email === 'dev@test.com' && password === 'dev123') {
      console.log('🔓 Development bypass activated')
      // Mock user object for testing
      const mockUser = {
        id: 'dev-user-123',
        email: 'dev@test.com',
        user_metadata: { name: 'Dev User' }
      }
      setUser(mockUser as any)
      return
    }
    
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })
    if (error) throw error
  }

  const signOut = async () => {
    const { error } = await supabase.auth.signOut()
    if (error) throw error
  }

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
