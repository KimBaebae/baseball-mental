import { router } from 'expo-router';
import { TeamChooser } from '../TeamChooser';

export default function TeamSettings() {
  return <TeamChooser onSaved={() => router.back()} />;
}
