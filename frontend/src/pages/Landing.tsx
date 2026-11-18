import { keycloak } from '../auth'

export default function Landing() {
  return (
    <div className="landing">
      <div className="brand big"><span className="brand-logo">1С</span>Ассистент</div>
      <h1>Спросите 1С обычными словами</h1>
      <p>Задайте вопрос про продажи, склад или расчёты — ассистент найдёт ответ в вашей базе и покажет, как его получил.</p>
      <button className="primary" onClick={() => keycloak.login()}>Войти</button>
      <ul className="landing-examples">
        <li>Выручка за сентябрь по филиалам</li>
        <li>Топ-10 клиентов за квартал</li>
        <li>Остатки на складах</li>
      </ul>
    </div>
  )
}
