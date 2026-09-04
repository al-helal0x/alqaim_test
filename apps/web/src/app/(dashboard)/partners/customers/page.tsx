import { PartnersListPage } from "@/features/partners/partners-list-page";

export default function CustomersPage() {
  return (
    <PartnersListPage
      partnerType="customer"
      title="العملاء"
      description="قائمة عملاء الشركة"
      createLabel="عميل جديد"
    />
  );
}
