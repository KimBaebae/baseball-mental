import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useState, type PropsWithChildren } from 'react';
import { isTeamId } from './domain/teams';

const STORAGE_KEY = '@baseball-mental/support-team';

type TeamPreference = {
  teamId: string | null;
  status: 'loading' | 'ready' | 'error';
  reload: () => void;
  selectTeam: (id: string) => Promise<void>;
};

const TeamPreferenceContext = createContext<TeamPreference | null>(null);

export function TeamPreferenceProvider({ children }: PropsWithChildren) {
  const [teamId, setTeamId] = useState<string | null>(null);
  const [status, setStatus] = useState<TeamPreference['status']>('loading');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    void AsyncStorage.getItem(STORAGE_KEY).then(saved => {
      if (!active) return;
      setTeamId(isTeamId(saved) ? saved : null);
      setStatus('ready');
    }).catch(() => { if (active) setStatus('error'); });
    return () => { active = false; };
  }, [attempt]);

  const reload = useCallback(() => { setStatus('loading'); setAttempt(value => value + 1); }, []);
  const selectTeam = useCallback(async (id: string) => {
    if (!isTeamId(id)) throw new Error('응원팀을 다시 선택해주세요.');
    await AsyncStorage.setItem(STORAGE_KEY, id);
    setTeamId(id);
  }, []);

  return <TeamPreferenceContext.Provider value={{ teamId, status, reload, selectTeam }}>
    {children}
  </TeamPreferenceContext.Provider>;
}

export function useTeamPreference(): TeamPreference {
  const preference = useContext(TeamPreferenceContext);
  if (!preference) throw new Error('TeamPreferenceProvider is missing');
  return preference;
}
