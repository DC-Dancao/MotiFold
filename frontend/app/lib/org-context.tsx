"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { fetchWithAuth, getApiUrl } from './api';

interface Organization {
  id: string;  // slug
  name: string;
  slug: string;
  status: 'provisioning' | 'active' | 'failed';
  created_at: string;
}

interface OrgContextType {
  organizations: Organization[];
  currentOrg: Organization | null;
  setCurrentOrg: (org: Organization | null) => void;
  refreshOrganizations: () => Promise<void>;
  isLoading: boolean;
}

const OrgContext = createContext<OrgContextType | null>(null);

function syncOrgCookie(orgSlug: string | null) {
  if (typeof document === 'undefined') {
    return;
  }

  if (orgSlug) {
    document.cookie = `motifold_current_org_id=${encodeURIComponent(orgSlug)}; path=/; samesite=lax`;
    return;
  }

  document.cookie = 'motifold_current_org_id=; path=/; max-age=0; samesite=lax';
}

export function OrgProvider({ children }: { children: React.ReactNode }) {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [currentOrg, setCurrentOrgState] = useState<Organization | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const refreshOrganizations = useCallback(async () => {
    setIsLoading(true);
    try {
      const apiUrl = getApiUrl();
      const response = await fetchWithAuth(`${apiUrl}/api/orgs/`, {
        credentials: 'include',
      });

      if (response.ok) {
        const orgs: Organization[] = await response.json();
        setOrganizations(orgs);

        // Auto-select first org if currentOrg is not set or no longer valid
        const storedOrgSlug = localStorage.getItem('motifold_current_org_id');
        const validOrg = orgs.find(o => o.slug === storedOrgSlug);
        if (validOrg) {
          setCurrentOrgState(validOrg);
          syncOrgCookie(validOrg.slug);
        } else if (orgs.length > 0) {
          setCurrentOrgState(orgs[0]);
          localStorage.setItem('motifold_current_org_id', orgs[0].slug);
          syncOrgCookie(orgs[0].slug);
        } else {
          syncOrgCookie(null);
        }
      }
    } catch (error) {
      console.error('Failed to fetch organizations:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const setCurrentOrg = useCallback((org: Organization | null) => {
    setCurrentOrgState(org);
    if (org) {
      localStorage.setItem('motifold_current_org_id', org.slug);
      syncOrgCookie(org.slug);
    } else {
      localStorage.removeItem('motifold_current_org_id');
      syncOrgCookie(null);
    }
  }, []);

  useEffect(() => {
    refreshOrganizations();
  }, []);

  return (
    <OrgContext.Provider value={{
      organizations,
      currentOrg,
      setCurrentOrg,
      refreshOrganizations,
      isLoading,
    }}>
      {children}
    </OrgContext.Provider>
  );
}

export function useOrg() {
  const context = useContext(OrgContext);
  if (!context) {
    throw new Error('useOrg must be used within OrgProvider');
  }
  return context;
}
