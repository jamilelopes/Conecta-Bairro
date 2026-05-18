import { useAuth } from '../../auth/use-auth';
import { PROFESSIONALS } from '../../mocks/fixtures/professionals';

const MOCK_USER = PROFESSIONALS[0];

function MenuItem({
  icon,
  label,
  active = false,
  danger = false,
  href = '#',
  onClick,
}: {
  icon: string;
  label: string;
  active?: boolean;
  danger?: boolean;
  href?: string;
  onClick?: () => void;
}) {
  return (
    <a
      href={href}
      onClick={onClick ? (e) => { e.preventDefault(); onClick(); } : undefined}
      className={
        active
          ? 'flex items-center gap-3 px-6 py-2.5 text-sm font-bold text-primary bg-violet-50 transition-colors'
          : danger
            ? 'flex items-center gap-3 px-6 py-2.5 text-sm text-red-500 hover:bg-red-50 transition-colors'
            : 'flex items-center gap-3 px-6 py-2.5 text-sm text-slate-600 hover:bg-slate-50 hover:text-primary transition-colors'
      }
    >
      <span
        className="material-symbols-outlined text-[20px]"
        style={active ? { fontVariationSettings: '"FILL" 1' } : undefined}
      >
        {icon}
      </span>
      {label}
    </a>
  );
}

export function UserDropdown() {
  const { identity, claims, signOut } = useAuth();
  const isMock = import.meta.env.PUBLIC_ENABLE_MOCK === 'true';

  console.log('UserDropdown render - identity:', identity, 'claims:', claims, isMock);

  if (!identity.userId && !isMock) return null;

  const avatarSrc = isMock ? MOCK_USER.avatarUrl : (claims?.picture ?? '')
  const userName = isMock ? MOCK_USER.name : (claims?.name ?? 'Usuário')

  return (
    <div className="relative ml-2 group/dd">
      <button className="flex items-center gap-2 p-1.5 rounded-full hover:bg-slate-100 transition-colors">
        <div className="w-9 h-9 rounded-full overflow-hidden border-2 border-primary/10 bg-slate-200 flex items-center justify-center">
          {avatarSrc ? (
            <img className="w-full h-full object-cover" src={avatarSrc} alt={userName} />
          ) : (
            <span className="material-symbols-outlined text-slate-400 text-xl">person</span>
          )}
        </div>
        <span className="material-symbols-outlined text-slate-400 text-lg group-hover/dd:rotate-180 transition-transform duration-300">
          expand_more
        </span>
      </button>
      <div className="invisible opacity-0 group-hover/dd:opacity-100 group-hover/dd:visible group-hover/dd:translate-y-0 absolute right-0 top-full mt-2 w-64 bg-white rounded-2xl shadow-xl border border-slate-100 py-3 transition-all duration-200 translate-y-2 origin-top-right z-50">
        <div className="px-6 py-3 mb-2 border-b border-slate-50">
          <p className="text-xs text-slate-500">Logado como</p>
          <p className="text-sm font-bold text-on-surface">{userName}</p>
        </div>
        <MenuItem icon="person" label="Meu Perfil" href="/profile" active />
        <div className="my-2 border-t border-slate-50" />
        <MenuItem icon="logout" label="Sair" danger href="#" onClick={signOut} />
      </div>
    </div>
  );
}
