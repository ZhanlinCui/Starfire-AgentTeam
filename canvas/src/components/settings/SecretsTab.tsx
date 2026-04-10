import { useSecretsStore } from '@/stores/secrets-store';
import { SERVICES, SERVICE_GROUP_ORDER } from '@/lib/services';
import { ServiceGroup } from './ServiceGroup';
import { SearchBar } from './SearchBar';
import { EmptyState } from './EmptyState';
import { AddKeyForm } from './AddKeyForm';

interface SecretsTabProps {
  workspaceId: string;
}

/**
 * Content of the "API Keys" tab inside SettingsPanel.
 * Orchestrates SearchBar, ServiceGroups, AddKeyForm, and EmptyState.
 */
export function SecretsTab({ workspaceId }: SecretsTabProps) {
  const secrets = useSecretsStore((s) => s.secrets);
  const isLoading = useSecretsStore((s) => s.isLoading);
  const error = useSecretsStore((s) => s.error);
  const isAddFormOpen = useSecretsStore((s) => s.isAddFormOpen);
  const setAddFormOpen = useSecretsStore((s) => s.setAddFormOpen);
  const fetchSecrets = useSecretsStore((s) => s.fetchSecrets);
  const grouped = useSecretsStore((s) => s.getGrouped());
  const searchQuery = useSecretsStore((s) => s.searchQuery);

  const SEARCH_THRESHOLD = 4;
  const showSearch = secrets.length >= SEARCH_THRESHOLD;

  // Panel load error
  if (error) {
    return (
      <div className="secrets-tab__error" role="alert">
        <p>{error}</p>
        <button
          onClick={() => fetchSecrets(workspaceId)}
          className="secrets-tab__refresh-btn"
        >
          Refresh
        </button>
      </div>
    );
  }

  // Loading
  if (isLoading) {
    return (
      <div className="secrets-tab__loading" aria-busy="true">
        Loading API keys…
      </div>
    );
  }

  // Empty state
  if (secrets.length === 0) {
    return (
      <>
        <EmptyState onAddFirst={() => setAddFormOpen(true)} />
        {isAddFormOpen && (
          <AddKeyForm
            workspaceId={workspaceId}
            existingNames={[]}
            onCancel={() => setAddFormOpen(false)}
          />
        )}
      </>
    );
  }

  // Check if search filtered everything out
  const totalFiltered = Object.values(grouped).reduce(
    (sum, arr) => sum + arr.length,
    0,
  );

  return (
    <div className="secrets-tab">
      {showSearch && <SearchBar />}

      {totalFiltered === 0 && searchQuery && (
        <div className="secrets-tab__no-results">
          No keys match &ldquo;{searchQuery}&rdquo;
          <button
            onClick={() => useSecretsStore.getState().setSearchQuery('')}
            className="secrets-tab__clear-search"
          >
            Clear search
          </button>
        </div>
      )}

      {SERVICE_GROUP_ORDER.map((groupKey) => {
        const groupSecrets = grouped[groupKey];
        if (groupSecrets.length === 0) return null;
        return (
          <ServiceGroup
            key={groupKey}
            group={groupKey}
            service={SERVICES[groupKey]}
            secrets={groupSecrets}
            workspaceId={workspaceId}
          />
        );
      })}

      <div className="secrets-tab__add-section">
        {isAddFormOpen ? (
          <AddKeyForm
            workspaceId={workspaceId}
            existingNames={secrets.map((s) => s.name)}
            onCancel={() => setAddFormOpen(false)}
          />
        ) : (
          <button
            onClick={() => setAddFormOpen(true)}
            className="secrets-tab__add-btn"
          >
            + Add API Key
          </button>
        )}
      </div>
    </div>
  );
}
