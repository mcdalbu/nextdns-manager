#!/bin/bash

# Define o arquivo de configuração do systemd-resolved
RESOLV_CONF="/etc/systemd/resolved.conf"

# Define o conteúdo para o NextDNS on
NEXTDNS_ON_CONTENT="
[Resolve]
DNSOverTLS=yes
DNS=45.90.28.0#Sirius-fd4e78.dns.nextdns.io
DNS=45.90.30.0#Sirius-fd4e78.dns.nextdns.io
"

# Função para exibir o menu e processar a escolha
menu() {
    echo "" # Linha em branco para melhor espaçamento
    echo "Selecione o método de DNS:"
    echo "1) NextDNS ON (aplicar configuração NextDNS)"
    echo "2) NextDNS OFF (apagar configuração NextDNS)"
    echo "3) DNS Status (mostrar status do resolvectl)"
    echo "4) Sair"

    read -p "Sua escolha: " choice

    case $choice in
        1)
            echo "Ativando NextDNS..."
            # Cria ou sobrescreve o arquivo resolved.conf com a configuração do NextDNS
            echo "$NEXTDNS_ON_CONTENT" | sudo tee "$RESOLV_CONF" > /dev/null
            echo "Configuração do NextDNS aplicada em $RESOLV_CONF."
            ;;
        2)
            echo "Desativando NextDNS..."
            if [ -f "$RESOLV_CONF" ]; then
                echo "Removendo configurações do NextDNS de $RESOLV_CONF..."
                sudo sed -i '/^DNSOverTLS=yes/d; /^DNS=45\.90\.28\.0#Sirius-fd4e78\.dns\.nextdns\.io/d; /^DNS=45\.90\.30\.0#Sirius-fd4e78\.dns\.nextdns\.io/d' "$RESOLV_CONF"
                echo "Configurações do NextDNS removidas de $RESOLV_CONF."
            else
                echo "Arquivo $RESOLV_CONF não encontrado, nada a remover."
            fi
            ;;
        3)
            echo "Mostrando status do DNS..."
            resolvectl status
            echo "Status do DNS exibido."
            return # Retorna para o loop principal sem reiniciar serviços
            ;;
        4)
            echo "Saindo..."
            exit 0 # Sai do script completamente
            ;;
        *)
            echo "Opção inválida. Por favor, escolha 1, 2, 3 ou 4."
            return # Retorna para o loop principal
            ;;
    esac

    # Estes comandos só serão executados se a opção 1 ou 2 for escolhida
    echo "Reiniciando o serviço systemd-resolved..."
    sudo systemctl restart systemd-resolved

    echo "Reiniciando o serviço NetworkManager..."
    sudo systemctl restart NetworkManager

    echo "Operação concluída!"
}

# Loop principal para manter o menu ativo
while true; do
    menu
done
